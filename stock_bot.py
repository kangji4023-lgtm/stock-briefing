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

KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY", "2e2432752d3bcaaf637aa44cfb75a555").strip()
KAKAO_REFRESH_TOKEN = os.getenv("KAKAO_REFRESH_TOKEN", "Pu-B2xW7jCGuYmeZsz2GC2B8_xM4bk73AAAAAgoXBi4AAAGf208W5Kj01SImjvGc").strip()
KAKAO_CLIENT_SECRET = os.getenv("KAKAO_CLIENT_SECRET", "2e2432752d3bcaaf637aa44cfb75a555").strip()

KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
KAKAO_SEND_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"


def require_secrets():
    missing = []
    if not KAKAO_REST_API_KEY:
        missing.append("KAKAO_REST_API_KEY")
    if not KAKAO_REFRESH_TOKEN:
        missing.append("KAKAO_REFRESH_TOKEN")
    if missing:
        raise RuntimeError("GitHub Secrets 누락: " + ", ".join(missing))


def get_kakao_access_token():
    require_secrets()

    data = {
        "grant_type": "refresh_token",
        "client_id": KAKAO_REST_API_KEY,
        "refresh_token": KAKAO_REFRESH_TOKEN,
    }

    # Client Secret을 사용하는 앱이면 GitHub Secret에 넣어 두면 자동 사용합니다.
    if KAKAO_CLIENT_SECRET:
        data["client_secret"] = KAKAO_CLIENT_SECRET

    r = requests.post(KAKAO_TOKEN_URL, data=data, timeout=20)
    print(f"[KAKAO TOKEN] HTTP {r.status_code}")

    if r.status_code != 200:
        raise RuntimeError(
            f"Kakao 토큰 발급 실패: HTTP {r.status_code} / {r.text}"
        )

    result = r.json()
    access_token = result.get("access_token")

    if not access_token:
        raise RuntimeError(f"access_token 없음: {result}")

    if result.get("refresh_token"):
        print("[KAKAO TOKEN] 새 refresh_token이 반환되었습니다. "
              "필요하면 GitHub Secret을 갱신하세요.")

    return access_token


def split_message(text, max_chars=190):
    """카카오 기본 text 템플릿의 200자 제한을 고려해 190자 이하로 분할."""
    text = str(text).strip()
    chunks = []

    while len(text) > max_chars:
        cut = text.rfind("\n", 0, max_chars + 1)

        if cut < max_chars // 2:
            cut = text.rfind(" ", 0, max_chars + 1)

        if cut < max_chars // 2:
            cut = max_chars

        chunks.append(text[:cut].strip())
        text = text[cut:].strip()

    if text:
        chunks.append(text)

    return chunks


def send_one_kakao_message(access_token, text):
    if len(text) > 200:
        raise ValueError(f"카카오 메시지가 200자를 초과했습니다: {len(text)}자")

    template_object = {
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
            template_object,
            ensure_ascii=False,
            separators=(",", ":"),
        )
    }

    r = requests.post(
        KAKAO_SEND_URL,
        headers=headers,
        data=data,
        timeout=20,
    )

    print(f"[KAKAO SEND] HTTP {r.status_code} / {r.text}")

    if r.status_code != 200:
        raise RuntimeError(
            f"Kakao 메시지 전송 실패: HTTP {r.status_code} / {r.text}"
        )


def send_kakao_report(parts):
    access_token = get_kakao_access_token()

    all_chunks = []
    for part_no, part in enumerate(parts, 1):
        chunks = split_message(part)
        for chunk_no, chunk in enumerate(chunks, 1):
            all_chunks.append((part_no, chunk_no, len(chunks), chunk))

    print(f"[KAKAO] 전체 전송 메시지 수: {len(all_chunks)}")

    for index, (part_no, chunk_no, part_total, chunk) in enumerate(
        all_chunks, 1
    ):
        print(
            f"[KAKAO] 전송 {index}/{len(all_chunks)} "
            f"(파트 {part_no}, {chunk_no}/{part_total}, {len(chunk)}자)"
        )

        send_one_kakao_message(access_token, chunk)
        time.sleep(0.7)

    print("[KAKAO] 전체 메시지 전송 완료")


def previous_weekday(date_str):
    d = datetime.strptime(date_str, "%Y%m%d")
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.strftime("%Y%m%d")


def get_krx_date():
    today = datetime.now(KST).strftime("%Y%m%d")

    try:
        d = stock.get_nearest_business_day_in_a_week(today)
        if d:
            return str(d)
    except Exception as e:
        print(f"[KRX DATE] pykrx 영업일 조회 실패: {e}")

    return previous_weekday(today)


def safe_float(value, default=None):
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def get_krx_market_data(date_str):
    result = {
        "date": date_str,
        "kospi": None,
        "kosdaq": None,
        "top5": [],
        "status": "정상",
    }

    # KOSPI
    try:
        k = stock.get_index_ohlcv_by_date(date_str, date_str, "1001")
        if not k.empty:
            result["kospi"] = {
                "close": safe_float(k["종가"].iloc[-1]),
                "rate": safe_float(k["등락률"].iloc[-1]),
            }
    except Exception as e:
        print(f"[KRX] KOSPI 오류: {e}")
        result["status"] = "일부 오류"

    # KOSDAQ
    try:
        kq = stock.get_index_ohlcv_by_date(date_str, date_str, "2001")
        if not kq.empty:
            result["kosdaq"] = {
                "close": safe_float(kq["종가"].iloc[-1]),
                "rate": safe_float(kq["등락률"].iloc[-1]),
            }
    except Exception as e:
        print(f"[KRX] KOSDAQ 오류: {e}")
        result["status"] = "일부 오류"

    # 국내 거래대금 TOP 5
    # 기존 코드의 get_market_trading_value_by_ticker()에서
    # '거래대금' 컬럼을 찾으면서 오류가 발생할 수 있으므로
    # OHLCV의 실제 '거래대금' 컬럼을 사용합니다.
    try:
        ohlcv = stock.get_market_ohlcv_by_ticker(
            date_str,
            market="ALL",
        )

        if not ohlcv.empty and "거래대금" in ohlcv.columns:
            top = ohlcv.sort_values(
                "거래대금",
                ascending=False,
            ).head(5)

            for ticker, row in top.iterrows():
                try:
                    name = stock.get_market_ticker_name(str(ticker))
                except Exception:
                    name = str(ticker)

                result["top5"].append(
                    {
                        "ticker": str(ticker),
                        "name": name,
                        "close": safe_float(row.get("종가"), 0),
                        "rate": safe_float(row.get("등락률"), 0),
                        "value": safe_float(row.get("거래대금"), 0),
                    }
                )
        else:
            result["status"] = "일부 오류"
            print("[KRX] 거래대금 컬럼 없음")

    except Exception as e:
        result["status"] = "일부 오류"
        print(f"[KRX] 거래대금 TOP5 오류: {e}")

    return result


def yf_history(symbol, period="5d", interval="1d", retries=3):
    last_error = None

    for attempt in range(1, retries + 1):
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(
                period=period,
                interval=interval,
                auto_adjust=False,
                actions=False,
            )

            if not df.empty:
                return df

            last_error = RuntimeError("빈 데이터")

        except Exception as e:
            last_error = e

        time.sleep(attempt)

    print(f"[YF] {symbol} 실패: {last_error}")
    return pd.DataFrame()


def get_latest_and_change(symbol):
    df = yf_history(symbol, "5d", "1d")

    if len(df) < 1:
        return None, None

    cur = safe_float(df["Close"].iloc[-1])
    prev = safe_float(df["Close"].iloc[-2]) if len(df) >= 2 else None

    rate = None
    if cur is not None and prev not in (None, 0):
        rate = (cur - prev) / prev * 100

    return cur, rate


def get_us_data():
    symbols = {
        "NASDAQ": "^IXIC",
        "S&P500": "^GSPC",
        "DOW": "^DJI",
    }

    result = {}

    for name, symbol in symbols.items():
        cur, rate = get_latest_and_change(symbol)
        result[name] = {
            "value": cur,
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
        cur, rate = get_latest_and_change(symbol)
        result[name] = {
            "value": cur,
            "rate": rate,
        }

    return result


def fmt_num(value, digits=2):
    if value is None:
        return "N/A"
    return f"{value:,.{digits}f}"


def fmt_rate(value):
    if value is None:
        return "N/A"
    return f"{value:+.2f}%"


def market_mood(krx, us):
    kr = krx.get("kospi", {}).get("rate")

    us_rates = [
        item.get("rate")
        for item in us.values()
        if item.get("rate") is not None
    ]

    if kr is not None and kr <= -1:
        return "하락 압력 / 변동성 주의"

    if kr is not None and kr >= 1:
        return "강한 상승 / 매수세 유입"

    if us_rates and min(us_rates) <= -1.5:
        return "글로벌 위험회피 주의"

    if us_rates and max(us_rates) >= 1.5:
        return "글로벌 위험선호 강화"

    return "중립 / 순환매 가능"


def classify_sector(name):
    n = str(name)

    if any(x in n for x in [
        "반도체",
        "하이닉스",
        "삼성전자",
        "한미반도체",
    ]):
        return "반도체·AI"

    if any(x in n for x in [
        "에코프로",
        "엘앤에프",
        "포스코",
        "배터리",
        "LG에너지",
    ]):
        return "2차전지·소재"

    if any(x in n for x in [
        "셀트리온",
        "삼성바이오",
        "제약",
        "바이오",
    ]):
        return "바이오·헬스케어"

    if any(x in n for x in [
        "한화",
        "현대로템",
        "방산",
        "한국항공",
    ]):
        return "방산·중공업"

    if any(x in n for x in [
        "현대차",
        "기아",
        "모비스",
    ]):
        return "자동차"

    return "기타"


def generate_report():
    now = datetime.now(KST)
    today = now.strftime("%Y-%m-%d")
    hour = now.hour

    if hour < 9:
        label = "오전 7시 미국장 마감 브리핑"
    elif hour < 13:
        label = "오전 11시 장중 브리핑"
    elif hour < 17:
        label = "오후 4시 국내장 마감 브리핑"
    else:
        label = "오후 7시 미국장 대응 브리핑"

    krx_date = get_krx_date()
    krx = get_krx_market_data(krx_date)
    us = get_us_data()
    macro = get_macro_data()

    mood = market_mood(krx, us)

    top5_lines = []

    for i, item in enumerate(krx["top5"], 1):
        sector = classify_sector(item["name"])

        top5_lines.append(
            f"{i}. {item['name']} "
            f"{fmt_num(item['close'], 0)}원 "
            f"({fmt_rate(item['rate'])}) "
            f"[{sector}]"
        )

    if not top5_lines:
        top5_lines.append("거래대금 데이터 조회 실패")

    top5_text = "\n".join(top5_lines)

    sector_counts = {}

    for item in krx["top5"]:
        sector = classify_sector(item["name"])
        sector_counts[sector] = sector_counts.get(sector, 0) + 1

    sectors = sorted(
        sector_counts.items(),
        key=lambda x: x[1],
        reverse=True,
    )

    sector_text = "\n".join(
        f"{i}. {name} ({count}개)"
        for i, (name, count) in enumerate(sectors[:3], 1)
    )

    if not sector_text:
        sector_text = "TOP 종목 기반 섹터 집계 대기"

    p1 = (
        f"📅 {today} {label} [1/3]\n"
        f"🌍 시장: {mood}\n"
        f"🇰🇷 KRX 기준일: {krx_date}\n"
        f"KOSPI: "
        f"{fmt_num(krx['kospi']['close']) if krx['kospi'] else 'N/A'} "
        f"({fmt_rate(krx['kospi']['rate']) if krx['kospi'] else 'N/A'})\n"
        f"KOSDAQ: "
        f"{fmt_num(krx['kosdaq']['close']) if krx['kosdaq'] else 'N/A'} "
        f"({fmt_rate(krx['kosdaq']['rate']) if krx['kosdaq'] else 'N/A'})\n"
        f"🔥 거래대금 TOP5\n"
        f"{top5_text}"
    )

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
        f"🔥 수급 상위 섹터\n"
        f"{sector_text}"
    )

    p3 = (
        f"🎯 투자 대응 [3/3]\n"
        f"① 시장: {mood}\n"
        f"② 대응: 거래대금 상위 + 상승추세 종목 우선 확인\n"
        f"③ 추격매수보다 눌림목/거래량 확인\n"
        f"⚠️ 환율 {fmt_num(macro['환율']['value'])}원, "
        f"VIX {fmt_num(macro['VIX']['value'])} 변동 주의\n"
        f"※ KRX/해외 데이터가 장중 지연·휴장일에는 "
        f"최근 거래일 기준으로 표시됩니다.\n"
        f"※ 투자판단은 본인 책임입니다."
    )

    return [p1, p2, p3]


def job():
    now = datetime.now(KST)

    print("=" * 70)
    print(f"[START] {now.isoformat()}")
    print("=" * 70)

    try:
        parts = generate_report()

        for i, part in enumerate(parts, 1):
            print(f"\n===== PART {i} =====")
            print(part)

        send_kakao_report(parts)

        print("[SUCCESS] 주식 브리핑 전송 완료")
        return 0

    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {e}")
        raise


if __name__ == "__main__":
    raise SystemExit(job())
