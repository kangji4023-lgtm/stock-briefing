import os
import json
import time
from datetime import datetime, timedelta

import pandas as pd
import pytz
import requests
import yfinance as yf
from pykrx import stock

KST = pytz.timezone("Asia/Seoul")

# =========================================================
# GitHub Secrets
# =========================================================
KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY", "2e2432752d3bcaaf637aa44cfb75a555").strip()
KAKAO_REFRESH_TOKEN = os.getenv("KAKAO_REFRESH_TOKEN", "Pu-B2xW7jCGuYmeZsz2GC2B8_xM4bk73AAAAAgoXBi4AAAGf208W5Kj01SImjvGc").strip()
KAKAO_CLIENT_SECRET = os.getenv("KAKAO_CLIENT_SECRET", "2e2432752d3bcaaf637aa44cfb75a555").strip()

TOKEN_URL = "https://kauth.kakao.com/oauth/token"
SEND_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"


# =========================================================
# 공통
# =========================================================
def fmt_num(value, digits=2):
    if value is None:
        return "N/A"
    try:
        return f"{float(value):,.{digits}f}"
    except Exception:
        return "N/A"


def fmt_rate(value):
    if value is None:
        return "N/A"
    try:
        return f"{float(value):+.2f}%"
    except Exception:
        return "N/A"


def safe_float(value):
    try:
        if value is None or pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None


def previous_weekday(date_str):
    d = datetime.strptime(date_str, "%Y%m%d")
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.strftime("%Y%m%d")


# =========================================================
# Kakao
# =========================================================
def get_kakao_access_token():
    if not KAKAO_REST_API_KEY:
        raise RuntimeError("KAKAO_REST_API_KEY가 없습니다.")

    if not KAKAO_REFRESH_TOKEN:
        raise RuntimeError("KAKAO_REFRESH_TOKEN이 없습니다.")

    data = {
        "grant_type": "refresh_token",
        "client_id": KAKAO_REST_API_KEY,
        "refresh_token": KAKAO_REFRESH_TOKEN,
    }

    if KAKAO_CLIENT_SECRET:
        data["client_secret"] = KAKAO_CLIENT_SECRET

    r = requests.post(TOKEN_URL, data=data, timeout=20)

    print(f"[KAKAO TOKEN] HTTP {r.status_code}")

    if r.status_code != 200:
        raise RuntimeError(
            f"Kakao 토큰 발급 실패: {r.status_code} / {r.text}"
        )

    result = r.json()

    token = result.get("access_token")

    if not token:
        raise RuntimeError(f"access_token 없음: {result}")

    # Kakao가 새 refresh_token을 반환한 경우 로그에만 표시
    # 실제 Secret 자동 갱신은 GitHub Actions에서 할 수 없으므로
    # 새 refresh_token은 필요 시 Secret을 수동 갱신해야 합니다.
    if result.get("refresh_token"):
        print("[KAKAO TOKEN] 새 refresh_token 반환됨")

    return token


def split_kakao_message(text, max_chars=190):
    """
    카카오 기본 text 템플릿의 200자 제한을 고려하여
    190자 이하로 안전하게 분할합니다.
    """
    text = str(text).strip()
    result = []

    while len(text) > max_chars:
        cut = text.rfind("\n", 0, max_chars + 1)

        if cut < 80:
            cut = text.rfind(" ", 0, max_chars + 1)

        if cut < 80:
            cut = max_chars

        result.append(text[:cut].strip())
        text = text[cut:].strip()

    if text:
        result.append(text)

    return result


def send_kakao_chunk(access_token, text):
    if len(text) > 200:
        raise ValueError(f"200자 초과 메시지: {len(text)}자")

    template = {
        "object_type": "text",
        "text": text,
        "link": {
            "web_url": "https://developers.kakao.com",
            "mobile_web_url": "https://developers.kakao.com",
        },
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
    }

    data = {
        "template_object": json.dumps(
            template,
            ensure_ascii=False,
            separators=(",", ":"),
        )
    }

    r = requests.post(
        SEND_URL,
        headers=headers,
        data=data,
        timeout=20,
    )

    print(f"[KAKAO SEND] HTTP {r.status_code}: {r.text}")

    if r.status_code != 200:
        raise RuntimeError(
            f"Kakao 메시지 전송 실패: {r.status_code} / {r.text}"
        )


def send_kakao_report(parts):
    token = get_kakao_access_token()

    chunks = []

    for part_no, part in enumerate(parts, 1):
        part_chunks = split_kakao_message(part)

        for chunk_no, chunk in enumerate(part_chunks, 1):
            chunks.append(
                (part_no, chunk_no, len(part_chunks), chunk)
            )

    print(f"[KAKAO] 총 {len(chunks)}개 메시지 전송")

    for i, (part_no, chunk_no, total, chunk) in enumerate(chunks, 1):
        print(
            f"[KAKAO] {i}/{len(chunks)} "
            f"파트={part_no} {chunk_no}/{total} "
            f"길이={len(chunk)}"
        )

        send_kakao_chunk(token, chunk)
        time.sleep(0.8)

    print("[KAKAO] 전체 전송 완료")


# =========================================================
# KRX
# =========================================================
def get_krx_date():
    today = datetime.now(KST).strftime("%Y%m%d")

    try:
        d = stock.get_nearest_business_day_in_a_week(today)

        if d:
            return str(d)

    except Exception as e:
        print(f"[KRX DATE] pykrx 조회 실패: {e}")

    # pykrx가 실패해도 절대로 프로그램을 종료하지 않음
    return previous_weekday(today)


def get_krx_data(date_str):
    result = {
        "date": date_str,
        "kospi": None,
        "kosdaq": None,
        "top5": [],
        "krx_ok": False,
    }

    # -------------------------------
    # KOSPI
    # -------------------------------
    try:
        df = stock.get_index_ohlcv_by_date(
            date_str,
            date_str,
            "1001",
        )

        if not df.empty:
            close = safe_float(df["종가"].iloc[-1])
            rate = safe_float(df["등락률"].iloc[-1])

            result["kospi"] = {
                "close": close,
                "rate": rate,
            }

    except Exception as e:
        print(f"[KRX] KOSPI 조회 실패: {e}")

    # -------------------------------
    # KOSDAQ
    # -------------------------------
    try:
        df = stock.get_index_ohlcv_by_date(
            date_str,
            date_str,
            "2001",
        )

        if not df.empty:
            close = safe_float(df["종가"].iloc[-1])
            rate = safe_float(df["등락률"].iloc[-1])

            result["kosdaq"] = {
                "close": close,
                "rate": rate,
            }

    except Exception as e:
        print(f"[KRX] KOSDAQ 조회 실패: {e}")

    # -------------------------------
    # 거래대금 TOP5
    # -------------------------------
    try:
        df = stock.get_market_ohlcv_by_ticker(
            date_str,
            market="ALL",
        )

        if not df.empty:
            if "거래대금" in df.columns:
                df = df.sort_values(
                    by="거래대금",
                    ascending=False,
                ).head(5)

                for ticker, row in df.iterrows():
                    try:
                        name = stock.get_market_ticker_name(
                            str(ticker)
                        )
                    except Exception:
                        name = str(ticker)

                    result["top5"].append(
                        {
                            "ticker": str(ticker),
                            "name": name,
                            "close": safe_float(row.get("종가")),
                            "rate": safe_float(row.get("등락률")),
                            "value": safe_float(row.get("거래대금")),
                        }
                    )

    except Exception as e:
        print(f"[KRX] 거래대금 TOP5 조회 실패: {e}")

    result["krx_ok"] = bool(
        result["kospi"]
        or result["kosdaq"]
        or result["top5"]
    )

    return result


# =========================================================
# Yahoo Finance
# =========================================================
def yf_history(symbol, period="5d", interval="1d"):
    last_error = None

    for attempt in range(1, 4):
        try:
            df = yf.download(
                symbol,
                period=period,
                interval=interval,
                auto_adjust=False,
                progress=False,
                threads=False,
            )

            if df is not None and not df.empty:
                # yfinance 버전에 따라 MultiIndex가 반환될 수 있음
                if isinstance(df.columns, pd.MultiIndex):
                    try:
                        df.columns = df.columns.get_level_values(0)
                    except Exception:
                        pass

                return df

        except Exception as e:
            last_error = e
            print(
                f"[YF] {symbol} attempt {attempt} 실패: {e}"
            )

        time.sleep(attempt)

    print(f"[YF] {symbol} 최종 실패: {last_error}")
    return pd.DataFrame()


def latest_yf(symbol):
    df = yf_history(symbol)

    if df.empty or "Close" not in df.columns:
        return None, None

    try:
        close = df["Close"].dropna()

        if close.empty:
            return None, None

        current = float(close.iloc[-1])

        previous = (
            float(close.iloc[-2])
            if len(close) >= 2
            else None
        )

        rate = None

        if previous not in (None, 0):
            rate = (current - previous) / previous * 100

        return current, rate

    except Exception as e:
        print(f"[YF] {symbol} 계산 오류: {e}")
        return None, None


def get_us_data():
    symbols = {
        "NASDAQ": "^IXIC",
        "S&P500": "^GSPC",
        "DOW": "^DJI",
    }

    result = {}

    for name, symbol in symbols.items():
        value, rate = latest_yf(symbol)

        result[name] = {
            "value": value,
            "rate": rate,
        }

    return result


def get_macro_data():
    symbols = {
        "환율": "USDKRW=X",
        "WTI": "CL=F",
        "미국채10년": "^TNX",
        "VIX": "^VIX",
    }

    result = {}

    for name, symbol in symbols.items():
        value, rate = latest_yf(symbol)

        result[name] = {
            "value": value,
            "rate": rate,
        }

    return result


# =========================================================
# 분석
# =========================================================
def classify_sector(name):
    name = str(name)

    if any(x in name for x in [
        "삼성전자",
        "하이닉스",
        "한미반도체",
        "반도체",
        "이오테크닉스",
    ]):
        return "반도체·AI"

    if any(x in name for x in [
        "에코프로",
        "엘앤에프",
        "포스코",
        "LG에너지",
        "삼성SDI",
        "배터리",
    ]):
        return "2차전지·소재"

    if any(x in name for x in [
        "셀트리온",
        "삼성바이오",
        "바이오",
        "제약",
    ]):
        return "바이오·헬스케어"

    if any(x in name for x in [
        "한화",
        "현대로템",
        "한국항공",
        "방산",
    ]):
        return "방산·중공업"

    if any(x in name for x in [
        "현대차",
        "기아",
        "현대모비스",
    ]):
        return "자동차"

    return "기타"


def get_market_mood(krx, us):
    rates = []

    if krx.get("kospi"):
        if krx["kospi"].get("rate") is not None:
            rates.append(krx["kospi"]["rate"])

    for x in us.values():
        if x.get("rate") is not None:
            rates.append(x["rate"])

    if not rates:
        return "데이터 확인 필요"

    if min(rates) <= -1.5:
        return "변동성 확대 / 하방압력 주의"

    if max(rates) >= 1.5:
        return "상승 모멘텀 강화"

    return "중립 / 순환매 가능"


def build_sector_text(top5):
    counts = {}

    for item in top5:
        sector = classify_sector(item["name"])
        counts[sector] = counts.get(sector, 0) + 1

    if not counts:
        return "거래대금 섹터 집계 불가"

    ordered = sorted(
        counts.items(),
        key=lambda x: x[1],
        reverse=True,
    )

    return "\n".join(
        f"{i}. {name} ({count}종목)"
        for i, (name, count) in enumerate(ordered[:3], 1)
    )


# =========================================================
# 리포트
# =========================================================
def generate_report():
    now = datetime.now(KST)
    today = now.strftime("%Y-%m-%d")

    if now.hour < 9:
        label = "오전 7시 미국장 마감"
    elif now.hour < 13:
        label = "오전 11시 장중"
    elif now.hour < 17:
        label = "오후 4시 국내장 마감"
    else:
        label = "오후 7시 미국장 대응"

    krx_date = get_krx_date()
    krx = get_krx_data(krx_date)

    # KRX가 실패해도 반드시 여기까지 진행
    us = get_us_data()
    macro = get_macro_data()

    mood = get_market_mood(krx, us)

    # -------------------------------
    # 국내 지수
    # -------------------------------
    if krx["kospi"]:
        kospi_text = (
            f"{fmt_num(krx['kospi']['close'])} "
            f"({fmt_rate(krx['kospi']['rate'])})"
        )
    else:
        kospi_text = "조회 실패"

    if krx["kosdaq"]:
        kosdaq_text = (
            f"{fmt_num(krx['kosdaq']['close'])} "
            f"({fmt_rate(krx['kosdaq']['rate'])})"
        )
    else:
        kosdaq_text = "조회 실패"

    # -------------------------------
    # 거래대금 TOP5
    # -------------------------------
    top_lines = []

    for i, item in enumerate(krx["top5"], 1):
        top_lines.append(
            f"{i}. {item['name']} "
            f"{fmt_num(item['close'], 0)}원 "
            f"({fmt_rate(item['rate'])})"
        )

    if not top_lines:
        top_lines = [
            "현재 KRX 거래대금 조회 불가",
            "최근 거래일 데이터 재조회 필요",
        ]

    top_text = "\n".join(top_lines)

    sector_text = build_sector_text(krx["top5"])

    # -------------------------------
    # 파트 1
    # -------------------------------
    p1 = (
        f"📅 {today} {label} [1/3]\n"
        f"🌍 시장: {mood}\n"
        f"🇰🇷 KRX 기준일: {krx_date}\n"
        f"KOSPI: {kospi_text}\n"
        f"KOSDAQ: {kosdaq_text}\n"
        f"🔥 거래대금 TOP5\n"
        f"{top_text}"
    )

    # -------------------------------
    # 파트 2
    # -------------------------------
    p2 = (
        f"📊 글로벌 증시 [2/3]\n"
        f"NASDAQ: {fmt_num(us['NASDAQ']['value'])} "
        f"({fmt_rate(us['NASDAQ']['rate'])})\n"
        f"S&P500: {fmt_num(us['S&P500']['value'])} "
        f"({fmt_rate(us['S&P500']['rate'])})\n"
        f"DOW: {fmt_num(us['DOW']['value'])} "
        f"({fmt_rate(us['DOW']['rate'])})\n"
        f"📈 거시지표\n"
        f"환율: {fmt_num(macro['환율']['value'])}원\n"
        f"WTI: ${fmt_num(macro['WTI']['value'])}\n"
        f"미국채10년: {fmt_num(macro['미국채10년']['value'])}\n"
        f"VIX: {fmt_num(macro['VIX']['value'])}\n"
        f"🔥 주도 섹터\n"
        f"{sector_text}"
    )

    # -------------------------------
    # 파트 3
    # -------------------------------
    p3 = (
        f"🎯 투자 대응 [3/3]\n"
        f"① 시장: {mood}\n"
        f"② 거래대금·거래량 동반 종목 우선 확인\n"
        f"③ 급등 추격보다 눌림목 확인\n"
        f"⚠️ 환율 {fmt_num(macro['환율']['value'])}원 / "
        f"VIX {fmt_num(macro['VIX']['value'])}\n"
        f"📌 KRX 오류 시 최근 거래일 재조회\n"
        f"※ 데이터 오류·휴장일에는 N/A가 표시될 수 있습니다.\n"
        f"※ 투자판단은 본인 책임입니다."
    )

    return [p1, p2, p3]


# =========================================================
# 실행
# =========================================================
def main():
    now = datetime.now(KST)

    print("=" * 70)
    print(f"START: {now.isoformat()}")
    print("=" * 70)

    # Secret 사전 확인
    print(
        "KAKAO_REST_API_KEY:",
        "OK" if KAKAO_REST_API_KEY else "MISSING",
    )
    print(
        "KAKAO_REFRESH_TOKEN:",
        "OK" if KAKAO_REFRESH_TOKEN else "MISSING",
    )
    print(
        "KAKAO_CLIENT_SECRET:",
        "SET" if KAKAO_CLIENT_SECRET else "NOT SET",
    )

    if not KAKAO_REST_API_KEY or not KAKAO_REFRESH_TOKEN:
        raise RuntimeError(
            "Kakao 필수 Secret이 없습니다."
        )

    parts = generate_report()

    for i, part in enumerate(parts, 1):
        print(f"\n===== PART {i} =====")
        print(part)

    send_kakao_report(parts)

    print("=" * 70)
    print("SUCCESS: 카카오 브리핑 전송 완료")
    print("=" * 70)


if __name__ == "__main__":
    main()
