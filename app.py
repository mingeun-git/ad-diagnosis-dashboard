"""리워드 광고 플랫폼 진단 — 통합 포트폴리오 대시보드.

무엇을 보여주는 화면인가
------------------------
데이터 스프린트 팀이 만든 **시스템 3개**(① 어뷰징 탐지 · ② 개인화 추천 · ③ 광고 선별·진단)를
하나의 이야기로 잇는다. 왼쪽 내비게이션 순서가 곧 이야기 순서다:

    왜 이 프로젝트인가 → 1차 EDA 신호 3개 → 가설 검증 → 진단·해법 → 시스템 3개 → 마무리

두 종류의 데이터가 섞여 있다 (섞지 말 것)
------------------------------------------
1. **앞단(스토리)** — 이미 끝난 분석의 결론. `story.py` 의 하드코딩 상수를 읽는다.
   원본은 프로젝트 루트 `통합_스토리라인.md` 이며, 화면 문구가 문서와 달라지면 **문서를 먼저 고친다.**
2. **뒷단(운영 화면)** — 광고 선별 시스템의 실제 산출물. 로컬 파케이 또는 BigQuery 에서
   **실시간으로 읽어** 계산한다. 이 파일이 직접 집계한다.

팀원 시스템 중 **① 어뷰징 탐지는 2026-08-25 에 자료를 받아 Ⅱ 화면을 실제 내용으로 채웠다**
(원본 `어뷰징시스템_재현폴더/` · 정리본 `팀원1_어뷰징탐지시스템_정리.md` · 상수는 `story.ABUSE_*`).
**② 개인화 추천은 아직 자료 수령 전**이라 `krds.placeholder()` 로 **빗금 점선 자리**만 남겨 뒀다 —
완성된 척하지 않는 것이 의도다. 자료가 오면 그 자리를 채우면 된다.

디자인
------
KRDS(대한민국 정부 디자인 시스템) v1.0.0.
색·서체·모서리는 `.streamlit/config.toml`, 레이아웃·컴포넌트는 `krds.py` 가 담당한다.
**이 파일에는 CSS 를 쓰지 않는다.** 생김새를 고칠 일이 생기면 `krds.py` 만 열면 된다.

데이터 소스
-----------
LOCAL(파케이) / BIGQUERY 로 전환 가능. `.streamlit/secrets.toml` 에:

    source  = "BIGQUERY"
    project = "your-project"
    dataset = "<데이터셋>"

실행: streamlit run dashboard/app.py
"""
from __future__ import annotations

import json
import pathlib
import sys

import pandas as pd
import streamlit as st

HERE = pathlib.Path(__file__).resolve().parent
DATA = HERE / "data"
ARTIFACTS = HERE.parent / "artifacts"

# `streamlit run` 은 스크립트 폴더를 sys.path 에 넣어 주지만, 다른 방식(AppTest·직접 import)
# 으로 실행하면 안 넣어 준다. 그러면 `import krds` 가 ModuleNotFoundError 로 죽는다.
# (2026-08-16 S08 페이지 렌더 테스트에서 실제로 발생)
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import krds  # noqa: E402  — 위 sys.path 설정 뒤에 와야 한다
import story  # noqa: E402  — 앞단 스토리의 확정 실측값(하드코딩)

st.set_page_config(page_title="리워드 광고 플랫폼 진단 — 통합 대시보드",
                   page_icon="🎯", layout="wide",
                   initial_sidebar_state="expanded")
krds.setup()

TABLES = ["mart_tag_performance", "mart_ad_scorecard",
          "mart_ad_risk_alert", "mart_media_tag_gap", "tag_effect",
          "feature_comparison", "model_comparison"]

# BigQuery 산출물 데이터셋에 실제로 존재하는 테이블만. 나머지는 BIGQUERY 모드에서도 로컬 파케이로 읽는다.
# tag_effect / feature_comparison / model_comparison 은 분석 중간 산출물이라 BQ로 올리지 않았다.
# 이 구분이 없으면 BIGQUERY 모드에서 'Not found: Table' 로 죽는다. (2026-08-09)
BQ_TABLES = {"mart_tag_performance", "mart_ad_scorecard",
             "mart_ad_risk_alert", "mart_media_tag_gap"}

# 시연용 합성 광고 식별 기준 (config.DEMO_IDX_MIN 과 같은 값)
DEMO_IDX_MIN = 990_000


# ────────────────────────────────────────────── 데이터 로드
def secret(key: str, default=None):
    """secrets.toml 이 **아예 없을 때도** 죽지 않고 기본값을 돌려준다.

    `hasattr(st, "secrets")` 로는 못 막는다. `st.secrets` 객체는 항상 존재하고,
    실제 예외는 `.get()` 이 파일을 파싱하는 순간 `StreamlitSecretNotFoundError` 로 터진다.
    Streamlit Cloud 에 Secrets 를 안 붙여넣고 배포하면 이 경로를 탄다.
    (2026-08-16 배포용 폴더에서 실제로 발생 — 기존 코드의 결함이었다)
    """
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default


@st.cache_resource(show_spinner=False)
def _bq_client():
    """BigQuery 클라이언트.

    로컬(내 맥)에서는 gcloud ADC 가 자동으로 잡히지만, Streamlit Cloud 같은 배포 환경에는
    gcloud 가 없다. 그래서 secrets 에 서비스계정 JSON 이 들어 있으면 그걸로 인증한다.
    """
    from google.cloud import bigquery
    project = st.secrets["project"]
    if "gcp_service_account" in st.secrets:
        from google.oauth2 import service_account
        creds = service_account.Credentials.from_service_account_info(
            dict(st.secrets["gcp_service_account"]))
        return bigquery.Client(project=project, credentials=creds)
    return bigquery.Client(project=project)          # 로컬: gcloud ADC 사용


@st.cache_data(show_spinner=False)
def load(name: str) -> pd.DataFrame:
    src = secret("source", "LOCAL")
    if src == "BIGQUERY" and name in BQ_TABLES:
        return _bq_client().query(
            f"SELECT * FROM `{st.secrets['project']}.{st.secrets['dataset']}.{name}`"
        ).to_dataframe()
    for base in (DATA, ARTIFACTS):
        p = base / f"{name}.parquet"
        if p.exists():
            return pd.read_parquet(p)
    return pd.DataFrame()


@st.cache_data(show_spinner=False)
def load_eval() -> dict:
    for base in (DATA, ARTIFACTS):
        p = base / "model_eval.json"
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    return {}


A = load("mart_tag_performance")
B = load("mart_ad_scorecard")
Cc = load("mart_ad_risk_alert")
D = load("mart_media_tag_gap")
LIFT = load("tag_effect")
EV = load_eval()

SOURCE = secret("source", "LOCAL")
HAS_DATA = not B.empty

MOCK = (str(B.get("model_version", pd.Series(["?"])).iloc[0]).upper() == "MOCK"
        if HAS_DATA and "model_version" in B.columns else False)
SNAPSHOT = str(B["snapshot_date"].max()) if HAS_DATA and "snapshot_date" in B else "-"
MODEL_VER = str(EV.get("model_version", "?"))


# ══════════════════════════════════════════════════════════ 사이드 내비게이션
# 순서 = 이야기 순서. 처음 보는 사람은 위에서 아래로 읽으면 된다.
NAV: list[tuple[str, list[tuple[str, str]]]] = [
    ("Ⅰ. 왜 이 프로젝트인가", [
        ("intro", "프로젝트 개요"),
        ("signals", "1차 EDA — 이상 신호 3개"),
        ("hypothesis", "가설 검증"),
        ("diagnosis", "진단 → 시스템 3개"),
    ]),
    ("Ⅱ. 시스템 ① 어뷰징 탐지", [
        ("sys_abuse", "개요 (팀원 1)"),
    ]),
    ("Ⅲ. 시스템 ② 개인화 추천", [
        ("sys_reco", "개요 (팀원 2)"),
    ]),
    ("Ⅳ. 시스템 ③ 광고 선별·진단", [
        ("sys_select", "어떻게 만들었나"),
        ("overview", "재고 진단"),
        ("scoreboard", "태그 성과 스코어보드"),
        ("friction", "마찰 분석"),
        ("cards", "광고 카드"),
        ("risk", "리스크 경보"),
        ("gap", "유통 갭"),
        ("newads", "신규 광고 진단"),
        ("validation", "검증 결과"),
    ]),
    ("Ⅴ. 마무리", [
        ("closing", "기술 스택 · 예상 반론"),
    ]),
]

# 파이프라인 산출물이 있어야만 그릴 수 있는 화면. 없으면 안내를 띄우고 멈춘다.
DATA_PAGES = {"overview", "scoreboard", "friction", "cards",
              "risk", "gap", "newads", "validation"}

if "page" not in st.session_state:
    st.session_state.page = "intro"

with st.sidebar:
    krds.nav_brand("리워드 광고 플랫폼 진단",
                   "데이터 스프린트 · 시스템 3개 통합")
    for group, items in NAV:
        krds.nav_group(group)
        for key, label in items:
            if st.button(label, key=f"nav_{key}", width="stretch",
                         type="primary" if st.session_state.page == key else "tertiary"):
                st.session_state.page = key
                st.rerun()

    krds.nav_group("데이터")
    krds.rows([
        ("데이터 소스", "BigQuery" if SOURCE == "BIGQUERY" else "로컬 파케이", ""),
        ("태깅 모델", MODEL_VER, ""),
        ("스냅샷", SNAPSHOT, ""),
        ("광고 수", f"{len(B):,}" if HAS_DATA else "미생성", ""),
    ], ranked=False)

PAGE = st.session_state.page

# ══════════════════════════════════════════════════════════ 공통 헤더
krds.masthead("<b>리워드 광고 플랫폼</b> · 데이터 스프린트 통합 대시보드",
              f"데이터 스냅샷 {SNAPSHOT}")

if MOCK:
    krds.alert("danger", "MOCK 데이터입니다",
               "태그 내용에 의미가 없습니다 — 배관(파이프라인) 검증용 실행 결과입니다.")

if PAGE in DATA_PAGES and not HAS_DATA:
    krds.page_header("산출물이 아직 없습니다", eyebrow="시스템 ③ 광고 선별·진단",
                     desc="이 화면은 파이프라인 산출물을 실시간으로 읽습니다.")
    krds.alert("danger", "먼저 파이프라인을 실행하세요",
               "<code>/usr/bin/python3 광고선별시스템/scripts/run_pipeline.py</code><br>"
               "앞단(Ⅰ~Ⅲ)과 <b>어떻게 만들었나</b> 화면은 산출물 없이도 볼 수 있습니다.")
    st.stop()


# ══════════════════════════════════════════════════════════ Ⅰ-1. 프로젝트 개요
if PAGE == "intro":
    krds.page_header(
        "리워드 광고 플랫폼을 진단하고, 시스템 3개로 고치기",
        eyebrow="Ⅰ. 왜 이 프로젝트인가",
        desc="운영 로그 31일치로 시작해 <b>“이 플랫폼은 건강하게 돌아가는가”</b>를 물었다. "
             "세 축(측정·수요·공급) 모두에서 이상 신호가 나왔고, "
             "문제 하나당 시스템 하나로 답했다.",
        meta=[("관측 기간", story.PERIOD), ("원본 클릭", "16,854,865건"),
              ("만든 시스템", "3개"), ("문서 기준", story.UPDATED)])

    krds.alert("information", "이 대시보드를 읽는 법",
               "왼쪽 내비게이션 <b>순서가 곧 이야기 순서</b>입니다. "
               "Ⅰ(왜) → Ⅱ·Ⅲ·Ⅳ(무엇을 만들었나) → Ⅴ(믿어도 되는 근거) 로 읽으면 "
               "처음 보셔도 “왜 시스템이 3개인가”까지 이해하실 수 있습니다. "
               "<b>Ⅳ 광고 선별·진단</b> 만 실제 산출물이 연결된 살아 있는 화면이고, "
               "Ⅱ·Ⅲ 은 팀원 자료 수령 전이라 자리만 잡아 뒀습니다.")

    krds.section("한 장 요약", "이 프로젝트가 어떤 순서로 결론에 도달했는가.")
    krds.flow(story.STORY_FLOW)

    krds.section("1. 무엇을 받았나 — 리워드 광고 플랫폼의 운영 로그")
    st.markdown(
        "유저가 광고 미션(앱 설치·가입 등)을 완수하면 포인트(리워드)를 받고, "
        "광고주가 낸 돈을 플랫폼과 매체(광고 지면을 가진 제휴 앱)가 나눈다.")
    krds.nodes(story.PLATFORM_NODES)
    krds.note(story.PLATFORM_NOTE)

    with st.expander("용어 4개만 알면 끝까지 읽을 수 있습니다", expanded=True):
        st.dataframe(pd.DataFrame(story.TERMS, columns=["용어", "뜻"]),
                     width="stretch", hide_index=True)

    krds.section("2. 받은 데이터 — 운영 로그 31일치", story.PERIOD)
    raw = pd.DataFrame(story.RAW_TABLES, columns=["테이블", "행수", "내용"])
    st.dataframe(raw.style.format({"행수": "{:,}"}), width="stretch", hide_index=True)
    krds.note("이 숫자는 <b>어뷰징 전처리 전</b>의 원본이다. "
              "이후 분석에서 쓰는 마트는 정제 후 3,346,345행이다 — "
              "왜 80%를 버려야 했는지는 <b>1차 EDA 신호 ①</b> 에서 다룬다.")

    krds.section("3. 출발 질문")
    krds.quote(f"<b>“{story.CORE_QUESTION}”</b>", "primary")
    st.markdown("리워드 플랫폼의 건강은 세 가지가 **동시에** 성립해야 한다. "
                "그래서 EDA 도 이 세 축을 따라 들어갔고, **세 축 모두에서 이상 신호가 나왔다.**")
    krds.cards([{"label": f"축 {i}", "value": name, "tone": t, "sub": desc}
                for i, ((name, desc), t) in enumerate(
                    zip(story.HEALTH_AXES, ["danger", "warning", "primary"]), 1)], cols=3)


# ══════════════════════════════════════════════════════════ Ⅰ-2. 1차 EDA
elif PAGE == "signals":
    krds.page_header(
        "1차 EDA — 거래의 3주체 모두에서 나온 이상 신호",
        eyebrow="Ⅰ. 왜 이 프로젝트인가",
        desc="데이터·유저·광고 각각을 따로 열어봤다. "
             "<b>세 곳 모두에서 하나씩 신호가 나왔고</b>, 그 셋이 나중에 시스템 3개가 된다.",
        meta=[("신호", "3개"), ("기준 데이터", "신호① 원본 / 신호②③ 정제 후 마트")])

    t1, t2, t3 = st.tabs(["① 데이터 — 트래픽이 비정상이다",
                          "② 유저 — 수요가 소진되고 있다",
                          "③ 광고 — 지면 배분이 품질과 무관하다"])

    # ── 신호 ① 데이터
    with t1:
        s = story.SIGNALS["data"]
        krds.section(f"신호 {s['no']} [{s['actor']}] {s['title']}", f"→ {s['verdict']}")
        krds.cards(s["cards"])
        krds.quote(s["conclusion"], "danger")

    # ── 신호 ② 유저
    with t2:
        s = story.SIGNALS["user"]
        krds.section(f"신호 {s['no']} [{s['actor']}] {s['title']}", f"→ {s['verdict']}")
        st.markdown("수요의 건강을 세 단계로 확인했다. "
                    "**머무는가 → 어떻게 유지되는가 → 남은 유저는 효율적인가.**")
        krds.cards(s["cards"])
        krds.quote(s["conclusion"], "warning")

        krds.section("(3) 남아서 많이 쓰는 유저조차 효율이 낮다", level=3)
        seg = pd.DataFrame(story.USER_SEGMENTS,
                           columns=["세그먼트", "디바이스", "디바이스 비중",
                                    "클릭 점유", "전환 점유", "CVR"])
        st.bar_chart(seg.set_index("세그먼트")["CVR"], color=krds.C["primary50"],
                     height=260)
        st.dataframe(
            seg.style.format({"디바이스": "{:,}", "디바이스 비중": "{:.1%}",
                              "클릭 점유": "{:.1%}", "전환 점유": "{:.1%}", "CVR": "{:.1%}"}),
            width="stretch", hide_index=True)
        krds.note(story.USER_SEGMENT_NOTE)
        krds.alert("gray", "예외 하나 — 초헤비 유저", story.USER_SEGMENT_EXCEPTION)

    # ── 신호 ③ 광고
    with t3:
        s = story.SIGNALS["ads"]
        krds.section(f"신호 {s['no']} [{s['actor']}] {s['title']}", f"→ {s['verdict']}")
        krds.cards(s["cards"])

        krds.section("쏠림 자체보다, 쏠림이 품질과 무관하다는 게 문제다", level=3)
        pareto = pd.DataFrame(
            {"클릭 점유율": [0.814, 0.186], "매출 점유율": [0.948, 0.052]},
            index=["클릭 상위 1% 광고", "나머지 99%"])
        st.bar_chart(pareto, height=260, color=[krds.C["primary50"], krds.C["point50"]])
        krds.note("CVR 상위 25% 광고(713개)의 유통은 클릭 중앙값 114건·매체 2곳으로, "
                  "나머지(122건·2곳)와 <b>차이가 없었다</b>. "
                  "좋은 광고라고 해서 더 많이 유통되지 않는다는 뜻이다.")

        krds.section("그럼 왜 품질대로 못 돌리나 — 알 방법이 없기 때문이다")
        krds.rows([(k, v, m) for k, v, m in story.WHY_BLIND], ranked=False)
        krds.quote(story.WHY_BLIND_CONCLUSION, "primary")


# ══════════════════════════════════════════════════════════ Ⅰ-3. 가설 검증
elif PAGE == "hypothesis":
    H = story.HYP_TOTAL
    krds.page_header(
        "가설 검증 — 신호를 확정 사실로",
        eyebrow="Ⅰ. 왜 이 프로젝트인가",
        desc="세 신호는 눈에 띄지만 아직 ‘인상’이다. "
             "우연인지 구조인지 가리기 위해 <b>가설을 세워 통계 검정</b>했다.",
        meta=[("검정한 가설", f"{H['n']}개"), ("지지", f"{H['support']}개"),
              ("기각·근거부족", f"{H['reject']}개")])

    krds.cards([
        {"label": "검정한 가설", "value": str(H["n"]), "unit": "개", "tone": "primary",
         "sub": "프로젝트 초기 14개 + 통합 단계 추가 1개(B5)"},
        {"label": "지지", "value": str(H["support"]), "unit": "개", "tone": "success",
         "sub": "구조가 확인된 것"},
        {"label": "기각 · 근거부족", "value": str(H["reject"]), "unit": "개", "tone": "point",
         "sub": "<b>기각도 결정에 기여했다</b> — 아래 설명"},
        {"label": "시스템 결정에 직결", "value": "10", "unit": "개", "tone": "information",
         "sub": "A군 2 · B군 5 · C군 3 — 이 화면에 정리"},
    ])

    krds.note("판정은 <code>이전작업/가설검증_분석_요약리포트.xlsx</code>(2026-07-31) 기준이다. "
              "발표 흐름에 맞게 일부 문장은 재구성했다 — 예: A2 원문은 "
              "“ADID 필수/비필수 광고는 이상행동 비율이 다를 것이다”로 "
              "<b>‘지지(방향은 통념과 반대)’</b> 판정이다. 원문 그대로는 요약리포트를 참조.")

    for g in story.HYP_GROUPS:
        krds.section(f"{g['title']}", f"→ {g['leads_to']}")
        # 표만 있으면 판정이 눈에 안 들어온다. 색이 붙은 배지 줄을 위에 하나 깐다.
        st.markdown(
            " ".join(krds.badge(f"{no} {verdict}",
                                krds.VERDICT_TONE.get(verdict, "gray"), square=True)
                     for no, _, verdict, _ in g["rows"]),
            unsafe_allow_html=True)
        df = pd.DataFrame(g["rows"], columns=["#", "가설", "판정", "핵심 수치"])
        st.dataframe(df, width="stretch", hide_index=True,
                     column_config={"가설": st.column_config.TextColumn(width="large"),
                                    "핵심 수치": st.column_config.TextColumn(width="large"),
                                    "판정": st.column_config.TextColumn(width="small")})
        krds.quote(f"<b>결론 {g['key']}</b> — {g['conclusion']}", g["tone"])

    krds.alert("gray", "기각된 가설도 버리지 않았다", story.HYP_REJECT_NOTE)


# ══════════════════════════════════════════════════════════ Ⅰ-4. 진단 → 시스템 3개
elif PAGE == "diagnosis":
    krds.page_header(
        "진단 → 결정 — 문제 3개, 시스템 3개",
        eyebrow="Ⅰ. 왜 이 프로젝트인가",
        desc="검증을 거치자 세 신호는 세 개의 <b>구조적 문제</b>로 확정됐다. "
             "그리고 셋 다 일회성 분석으로는 풀 수 없다.",
        meta=[("문제", "3개"), ("시스템", "3개"), ("담당", "본인 1 · 팀원 2")])

    krds.quote(story.WHY_SYSTEM_NOT_REPORT, "danger")

    krds.section("문제 → 시스템 매핑")
    for s in story.SYSTEMS:
        krds.syscard(s["no"], s["name"], s["owner"], s["problem_title"], s["problem"],
                     s["does"], tone=s["tone"], mine=s["mine"])
    krds.note(story.SUPPLY_DEMAND_NOTE)

    krds.section("작업 순서에도 논리가 있다 — 어뷰징이 먼저다")
    krds.nodes([
        ("① 어뷰징 탐지", "오염 클릭 80.15% 제거", "danger"),
        ("깨끗한 데이터마트", "3,346,345행 · CVR 42.56%", "gray"),
        ("② 추천 / ③ 선별", "②는 유저 행동을, ③은 CVR 을 정답으로 학습", "primary"),
    ])
    krds.quote(story.DEPENDENCY_NOTE, "gray")

    krds.section("시스템끼리 서로를 먹여 살린다")
    for a, b, c in story.CROSS_LINKS:
        krds.alert("information" if a.startswith("③") else "gray", f"{a} · {b}", c)


# ══════════════════════════════════════════════════════════ Ⅱ. 어뷰징 탐지 (팀원 1)
# 2026-08-25: 팀원 1 자료 수령 → 자리표시(placeholder) 를 실제 내용으로 대체했다.
# 여기 숫자는 전부 story.ABUSE_* 상수다. 우리가 재계산하지 않는다 (CLAUDE.md D14).
elif PAGE == "sys_abuse":
    AB = story.ABUSE_BEFORE_AFTER
    krds.page_header(
        "시스템 ① 어뷰징 탐지",
        eyebrow="Ⅱ. 담당 — 팀원 1",
        desc="<b>문제 A. 측정의 문제</b> — 클릭의 80.15%가 비정상 트래픽이다. "
             "이대로면 플랫폼의 모든 성과 지표가 거짓이다.",
        meta=[("담당", "팀원 1"), ("상태", "자료 수령 완료 · 2026-08-25"),
              ("모델", "Isolation Forest"), ("분석 단위", "Device-Day")])

    krds.alert("information", "이 화면의 숫자는 팀원 1 의 산출물이다",
               story.ABUSE_D14_NOTE)

    # ── ① 가장 먼저 갈라야 할 것: 전처리 ≠ 탐지 시스템
    krds.section("먼저 갈라야 할 두 가지", "전처리(청소)와 탐지 시스템은 다른 것이다")
    two = pd.DataFrame(story.ABUSE_TWO_THINGS,
                       columns=["구분", "(가) 어뷰징 전처리", "(나) 어뷰징 탐지 시스템"])
    st.dataframe(two, width="stretch", hide_index=True,
                 column_config={
                     "(가) 어뷰징 전처리": st.column_config.TextColumn(width="large"),
                     "(나) 어뷰징 탐지 시스템": st.column_config.TextColumn(width="large")})
    krds.note(story.ABUSE_TWO_THINGS_NOTE)

    # ── ② (가) 전처리 — 정제 전후
    krds.section("(가) 전처리 — 이 격차가 시스템의 존재 이유다")
    krds.cards([
        {"label": "클릭 (정제 전 → 후)",
         "value": f"{AB['before_clicks']:,}", "tone": "gray",
         "sub": f"→ <b>{AB['after_clicks']:,}행</b> · {AB['removed_rate']:.2%} 제거"},
        {"label": "CVR (정제 전)", "value": f"{AB['before_cvr']:.2%}", "tone": "danger",
         "sub": "클릭 11번 중 10번이 헛클릭"},
        {"label": "CVR (정제 후)", "value": f"{AB['after_cvr']:.2%}", "tone": "success",
         "sub": "이 프로젝트의 모든 분석이 쓰는 기준"},
        {"label": "삭제 규칙", "value": f"{len(story.ABUSE_RULES)}", "unit": "개",
         "tone": "primary", "sub": "행동 패턴 기반"},
    ])
    st.bar_chart(pd.DataFrame({"CVR": [AB["before_cvr"], AB["after_cvr"]]},
                              index=["정제 전 (원본)", "정제 후 (마트)"]),
                 color=krds.C["primary50"], height=250)
    krds.note("CVR 을 외부에 인용할 때는 <b>반드시 “어뷰징 전처리 후”를 병기</b>한다. "
              "42.56%만 떼어 말하면 실제보다 5배 좋은 플랫폼처럼 들린다.")

    with st.expander("행동 패턴 규칙 6개 — 전처리 단계에서 확립"):
        ru = pd.DataFrame(story.ABUSE_RULES, columns=["규칙", "조건", "삭제 규모(행)"])
        st.dataframe(ru.style.format({"삭제 규모(행)": "{:,}"}), width="stretch",
                     hide_index=True,
                     column_config={"조건": st.column_config.TextColumn(width="large")})
        krds.note(f"근거: {story.ABUSE_SRC} · "
                  "규칙 R3 하나가 삭제량의 대부분(13,438,200행)을 차지한다 — "
                  "매체 1곳이 6일간 일으킨 봇성 폭주다. "
                  "<b>“전체 클릭의 80%”라는 규모는 사실상 이 사건 하나에서 나온다.</b>")

    # ── ③ (나) 상시 탐지 시스템 — 설계 원칙
    krds.section("(나) 상시 탐지 시스템 — 설계 원칙")
    krds.quote(story.ABUSE_PRINCIPLE, "danger")

    krds.section("파이프라인 4단계")
    krds.flow([(no, f"{name} — {head}", sub)
               for no, name, head, sub in story.ABUSE_PIPELINE])

    # ── ④ 모델
    krds.section("모델 — Isolation Forest", "정답 라벨이 없으므로 비지도 이상탐지를 쓴다")
    krds.cards([
        {"label": "알고리즘", "value": "Isolation Forest", "tone": "primary",
         "sub": "비지도 — 정답 라벨 불필요"},
        {"label": "트리 수", "value": "200", "unit": "개", "tone": "gray",
         "sub": "<code>n_estimators</code>"},
        {"label": "이상 비율", "value": "auto", "tone": "success",
         "sub": "<b>미리 정하지 않는다</b> · <code>contamination</code>"},
        {"label": "후보 기준", "value": "상위 1", "unit": "%", "tone": "warning",
         "sub": "어뷰징 기준이 아니라 <b>운영 threshold</b>"},
    ])
    krds.rows([(k, v, m) for k, v, m in story.ABUSE_FEATURES], ranked=False)
    krds.note(story.ABUSE_FEATURES_EXCLUDED)

    # ── ⑤ 반복 클릭 규칙
    krds.section("반복 클릭 규칙 3개", "Isolation Forest 가 놓치는 극단적 반복을 잡는다")
    rr = pd.DataFrame(story.ABUSE_REPEAT_RULES,
                      columns=["신호", "상대 기준 (매체 내 비교)", "절대 하한"])
    st.dataframe(rr, width="stretch", hide_index=True,
                 column_config={
                     "상대 기준 (매체 내 비교)": st.column_config.TextColumn(width="large")})
    krds.note(story.ABUSE_REPEAT_NOTE)

    # ── ⑥ 결합 → Risk Level
    krds.section("결합 → 최종 Risk Level")
    krds.cards([{"label": f"{code} — {ko}", "value": "", "tone": tn, "sub": cond}
                for code, ko, cond, tn in story.ABUSE_RISK_LEVELS], cols=3)
    krds.note(story.ABUSE_COMBINE_NOTE)

    # ── ⑦ 안 한 것과 그 이유
    krds.section("★ 안 한 것과 그 이유", "기각된 신호 — 이쪽이 더 중요하다")
    for what, why in story.ABUSE_REJECTED:
        krds.alert("gray", what, why)
    krds.note("우리 선별 시스템이 실패한 게이트(마찰 개수 상관 −0.07)를 지우지 않고 "
              "리포트에 남긴 것과 같은 태도다. <b>안 한 이유를 적어 두면 그것도 결과다.</b>")

    # ── ⑧ 이상 신호 3개의 겹침
    krds.section("이상 신호 3개는 따로 오지 않는다", "전체 Device-Day 1,985,804 기준")
    ov = pd.DataFrame(story.ABUSE_SIGNAL_OVERLAP, columns=["조건", "Device-Day"])
    ov["전체 대비"] = ov["Device-Day"] / 1_985_804
    st.bar_chart(ov.set_index("조건")["Device-Day"],
                 color=krds.C["primary50"], height=260)
    st.dataframe(ov.style.format({"Device-Day": "{:,}", "전체 대비": "{:.2%}"}),
                 width="stretch", hide_index=True)
    krds.note(story.ABUSE_SIGNAL_OVERLAP_NOTE)

    # ── ⑨ 우리가 재계산해 대조한 결과
    krds.section("우리가 그 숫자를 직접 확인했다",
                 "팀원 1 의 EDA 수치를 우리 원본 파케이로 재계산 (2026-08-25)")
    vf = pd.DataFrame([(k, a, b, "✅ 일치" if ok else "⚠️ 원본 문서가 갈림")
                       for k, a, b, ok in story.ABUSE_EDA_VERIFY],
                      columns=["항목", "팀원 1 값", "우리 재계산", "판정"])
    st.dataframe(vf, width="stretch", hide_index=True,
                 column_config={"항목": st.column_config.TextColumn(width="large")})
    krds.quote(story.ABUSE_EDA_VERIFY_NOTE, "success")
    krds.alert("information", "덤 — ads_type 코드 3 은 “설치형”이 아니라 “참여형”이다",
               story.ADS_TYPE_FIX_NOTE)
    with st.expander("ads_type 코드표 12종 (팀원 1 자료로 확정)"):
        st.dataframe(pd.DataFrame(sorted(story.ADS_TYPE_MAP.items()),
                                  columns=["코드", "광고 유형"]),
                     width="stretch", hide_index=True)

    # ── ⑨-B 우리 로컬 재현 (2026-08-25)
    krds.section("우리 환경에서 직접 돌려 봤다", "권한이 없어 조회가 안 되니, 재현했다")
    krds.alert("warning", "이 블록은 “우리 재현본”이지 팀원 1 의 공식 결과가 아니다",
               story.ABUSE_REPRO_NOTE)
    RV = story.ABUSE_REPRO_VERIFY
    krds.cards([
        {"label": "팀원 기준값 대조", "value": f"{RV['passed']}/{RV['total']}",
         "tone": "success", "sub": RV["basis"]},
        {"label": "재현한 Device-Day", "value": "1,985,804", "tone": "primary",
         "sub": "팀원 값과 <b>정확히 일치</b>"},
        {"label": "정제 후 이상 Device", "value": "8,569", "unit": "명",
         "tone": "warning", "sub": "전체의 0.93% · 마트 클릭의 <b>18.0%</b> 차지"},
        {"label": "반복클릭 극단 Device", "value": "126", "unit": "명",
         "tone": "danger", "sub": "정제 전 1,138명 → <b>−88.9%</b>"},
    ])

    krds.section("같은 잣대를 정제 전/후에 대 봤다", "우리 전처리가 표적을 맞췄나")
    ce = pd.DataFrame(story.ABUSE_CLEANING_EFFECT,
                      columns=["항목", "정제 전 (원본)", "정제 후 (마트)", "감소율"])
    st.dataframe(ce.style.format({"정제 전 (원본)": "{:,}", "정제 후 (마트)": "{:,}",
                                  "감소율": "{:.1%}"}), width="stretch", hide_index=True)
    krds.quote(story.ABUSE_CLEANING_NOTE, "success")
    krds.alert("danger", "그런데도 완결이 아니다", story.ABUSE_RESIDUAL_NOTE)
    rl = pd.DataFrame([(a, b, c) for a, b, c, _ in story.ABUSE_RESIDUAL_LEVELS],
                      columns=["등급", "Device 수", "하루 평균 클릭"])
    st.dataframe(rl.style.format({"Device 수": "{:,}", "하루 평균 클릭": "{:.1f}"}),
                 width="stretch", hide_index=True)

    # ── ⑨-C ①×③ 연결 — 우리 주장이 틀렸다
    krds.section("★ ①과 ③을 실제로 붙여 봤다", "그리고 우리 주장이 틀렸다는 걸 알았다")
    krds.quote(story.ABUSE_LINK_QUESTION, "primary")
    krds.flow(story.ABUSE_LINK_STEPS)

    krds.section("결정적 비교 — Device 클릭량을 통제하면",
                 "각 칸 = 그 집단의 클릭 중 ‘어뷰징유인’ 광고가 차지한 비중")
    bk = pd.DataFrame([(b, n, r, ("—" if h is None else f"{h:.2f}%"), memo)
                       for b, n, r, h, memo in story.ABUSE_LINK_BUCKETS],
                      columns=["Device 총 클릭", "정상 (%)", "REVIEW (%)", "HIGH", "표본"])
    st.dataframe(bk.style.format({"정상 (%)": "{:.2f}", "REVIEW (%)": "{:.2f}"}),
                 width="stretch", hide_index=True,
                 column_config={"표본": st.column_config.TextColumn(width="medium")})
    krds.quote(story.ABUSE_LINK_VERDICT, "danger")
    krds.alert("information", "그래도 논지는 무너지지 않는다 — 오히려 정확해진다",
               story.ABUSE_LINK_SILVER_LINING)
    krds.note(story.ABUSE_LINK_HONESTY)

    # ── ⑨-C-2 민감도 검정 — 이 기각이 우리 규칙 탓인가
    krds.section("이 기각이 우리가 정한 규칙 때문은 아닌가", "정의 3가지로 다시 재봤다")
    krds.alert("warning", "판정의 약점을 먼저 말한다", story.ABUSE_SENSITIVITY_WHY)
    sn = pd.DataFrame([(d, r, n, k, v) for d, r, n, k, v in story.ABUSE_SENSITIVITY],
                      columns=["등급 정의", "규칙", "30클릭+ 정상 (%)",
                               "30클릭+ 위험 (%)", "판정"])
    st.dataframe(sn.style.format({"30클릭+ 정상 (%)": "{:.2f}",
                                  "30클릭+ 위험 (%)": "{:.2f}"}),
                 width="stretch", hide_index=True,
                 column_config={"규칙": st.column_config.TextColumn(width="large")})
    krds.quote(story.ABUSE_SENSITIVITY_VERDICT, "success")
    krds.note(story.ABUSE_PERCENTILE_TEST)

    krds.section("팀원 1 에게 남은 요청", "3건 → 1건으로 줄었다")
    for name, state, tone, why in story.ABUSE_REQUESTS:
        krds.alert(tone if tone != "success" else "information",
                   f"{name} — {state}", why)

    # ── ⑨-D 범위 대조
    krds.section("두 시스템의 범위 대조", "어디까지 같고, 어디서 갈리고, 무엇을 맞췄나")
    sc = pd.DataFrame(story.ABUSE_SCOPE_DIFF,
                      columns=["축", "① 어뷰징 탐지", "③ 광고 선별", "맞춰야 하나"])
    st.dataframe(sc, width="stretch", hide_index=True,
                 column_config={"① 어뷰징 탐지": st.column_config.TextColumn(width="medium"),
                                "③ 광고 선별": st.column_config.TextColumn(width="medium"),
                                "맞춰야 하나": st.column_config.TextColumn(width="large")})
    krds.alert("warning", "적립 기준이 서로 달랐다 — 우리 기준으로 통일했다", story.ABUSE_RWD_GAP)

    # ── ⑩ 자동화 · 화면
    krds.section("자동화 · 운영 화면")
    krds.rows([(k, v, m) for k, v, m in story.ABUSE_OPS], ranked=False)

    # ── ⑪ 한계
    krds.section("한계 — 팀원 1 이 먼저 밝힌 것")
    for k, v in story.ABUSE_LIMITS:
        krds.alert("warning", k, v)

    # ── ⑫ 시스템 간 연결
    krds.section("이 시스템이 나머지 둘에게 주는 것")
    krds.rows([
        ("② 개인화 추천", "오염 없는 유저 행동", "봇의 클릭을 ‘선호’로 배우지 않게 한다"),
        ("③ 광고 선별·진단", "오염 없는 CVR 라벨", "CVR 8.75%라는 가짜 정답을 학습하지 않게 한다"),
    ], ranked=False)
    krds.alert("information", "아직 안 한 일 — ①과 ③을 실제로 붙이기", story.ABUSE_LINK_TODO)

    # ── ⑬ 재현 시 막히는 곳 (정직하게 남긴다)
    with st.expander("재현하려면 — 지금 막히는 곳 4가지"):
        st.dataframe(pd.DataFrame(story.ABUSE_REPRO_BLOCKERS, columns=["막히는 곳", "내용"]),
                     width="stretch", hide_index=True,
                     column_config={"내용": st.column_config.TextColumn(width="large")})
        krds.note(f"원본 자료: <code>{story.ABUSE_SRC_SYSTEM}</code> · "
                  f"상세 정리: <code>{story.ABUSE_DOC}</code>. "
                  "팀원 1 의 환경에서는 돌았다 — 위는 <b>공유 패키지의 누락·환경 차이</b>이지 "
                  "결과의 결함이 아니다.")


# ══════════════════════════════════════════════════════════ Ⅲ. 개인화 추천 (팀원 2)
elif PAGE == "sys_reco":
    krds.page_header(
        "시스템 ② 개인화 추천",
        eyebrow="Ⅲ. 담당 — 팀원 2",
        desc="<b>문제 B. 수요의 문제</b> — 유저 64.7%가 하루 만에 떠나고, "
             "많이 쓰는 유저일수록 효율이 낮다(헤비 CVR 35.7%). "
             "“무엇을 보여주느냐”를 유저별로 바꿔야 한다.",
        meta=[("담당", "팀원 2"), ("상태", "자료 수령 전"),
              ("확정된 것", "성립 근거 B1~B5")])

    krds.alert("warning", "이 화면은 아직 미완성입니다",
               "아래 <b>성립 근거</b>는 가설 검증으로 확인된 실측이고, "
               "<b>모델·평가</b> 부분은 팀원 2 자료 수령 후 채웁니다.")

    krds.section("접근")
    st.markdown(story.RECO_APPROACH, unsafe_allow_html=True)

    krds.section("성립 근거 — 개인화의 재료가 데이터에 실재하는가")
    krds.rows([(k, v, m) for k, v, m in story.RECO_BASIS], ranked=False)
    krds.quote("선호는 <b>뚜렷하고 · 지속되고 · 예측 가능하다.</b> "
               "그리고 무차별 노출의 효율은 이미 꺾여 있다(B5). "
               "개인화 추천이 성립할 <b>필요와 조건이 모두</b> 확인됐다.", "warning")

    krds.section("여기부터는 팀원 2 자료")
    krds.placeholder(
        "content-based 추천 모델",
        "유저 행동과 광고 속성을 어떻게 매칭했는지, 그리고 그 추천이 실제로 좋은지를 "
        "아래 항목으로 채운다.",
        story.PLACEHOLDER_ITEMS["reco"])

    krds.section("③ 선별 시스템에서 받아 가는 것")
    krds.alert("information", "15축 태그 = 추천의 아이템 feature",
               "추천 시스템은 <b>광고의 특징 없이는 성립하지 않는다.</b> "
               "그런데 기존에 쓸 수 있던 광고 feature 는 "
               "<code>ads_category</code>(88.9%가 한 값) 뿐이었다. "
               "선별 시스템이 만든 15축 태그가 그 자리를 대신한다 — "
               "<b>Ⅳ. 광고 선별·진단 → 태그 성과 스코어보드</b> 에서 실제 값을 볼 수 있다.")


# ══════════════════════════════════════════════════════════ Ⅳ-1. 어떻게 만들었나
elif PAGE == "sys_select":
    HO = story.HOLDOUT
    RS = story.ROLE_SPLIT
    krds.page_header(
        "시스템 ③ 광고 선별·진단 — 어떻게 만들었나",
        eyebrow="Ⅳ. 담당 — 본인",
        desc="<b>문제 C. 공급의 문제</b> — 하루 254개씩 들어오는 신규 광고"
             "(수명 중앙값 3일)를 성과 이력 없이 평가할 수단이 없다. "
             "<b>남은 정보는 텍스트뿐이었다.</b>",
        meta=[("담당", "본인"), ("상태", "완료 · 운영 중"),
              ("태깅 텍스트", "7,607건"), ("산출물", "4종")])

    krds.section("왜 텍스트인가")
    krds.rows([
        ("기존 분류축 ads_category", "88.9%", "13개 코드 중 하나가 이만큼 — 분류가 아니다"),
        ("기존 분류축 ads_type", "94.2%", "코드 3(참여형) 하나가 이만큼"),
        ("서로 다른 설명문", "1,438개", "제목은 7,475개인데 설명문은 대부분 붙여넣기 문구"),
        ("글자까지 같은 528개 광고의 CVR", "2.6~85.6%", "설명문 단독으로는 원리적으로 구분 불가"),
    ], ranked=False)
    krds.quote("그래서 <b>제목 + 설명문을 함께</b> 쓴다. 역할이 다르기 때문이다 — "
               "<b>제목</b>이 “무엇을 광고하나”를, <b>설명문</b>이 “무엇을 시키나”를 담당한다.",
               "primary")

    krds.section("파이프라인 6단계")
    krds.flow([(no, f"{name} — {head}", sub) for no, name, head, sub in story.SELECT_PIPELINE])

    krds.section("실험으로 확정한 역할 분리",
                 "예측 정확도만 겨루면 LLM 태그가 원시 텍스트 통계에 진다. 그래서 둘 다 쓴다.")
    krds.cards([
        {"label": "LLM 태그만 (R²)", "value": f"{RS['tag_r2']:.3f}", "tone": "warning",
         "sub": "15개 축으로 압축한 결과"},
        {"label": "텍스트 피처만 (R²)", "value": f"{RS['text_r2']:.3f}", "tone": "success",
         "sub": "TF-IDF/SVD · API 비용 0원"},
    ], cols=2)
    krds.note(RS["why"])
    krds.quote(RS["but"], "primary")
    krds.rows([(k, v, m) for k, v, m in RS["decision"]], ranked=False)

    krds.section("성능 — 학습에 한 번도 안 쓴 신생 광고로 시험",
                 f"{HO['desc']} · {HO['n']:,}개")
    hg = pd.DataFrame(HO["grades"], columns=["등급", "광고 수", "실제 CVR"])
    st.bar_chart(hg.set_index("등급")["실제 CVR"], color=krds.C["primary50"], height=280)
    st.dataframe(hg.style.format({"광고 수": "{:,}", "실제 CVR": "{:.1%}"}),
                 width="stretch", hide_index=True)
    krds.quote(
        f"성과 기록이 <b>하나도 없는</b> 광고를 제목과 설명문만 읽고 매긴 등급이, "
        f"실제 전환율을 <b>{HO['ratio']}배</b> 갈라낸다 "
        f"(D {HO['grades'][0][2]:.1%} vs S {HO['grades'][-1][2]:.1%} · "
        f"순위 상관 Spearman {HO['spearman']}).", "success")

    krds.section("산출물 4종 — 운영진이 실제로 쓰는 것")
    out = pd.DataFrame([(k, n, d, f"{sz:,}행") for k, n, d, sz, _ in story.SELECT_OUTPUTS],
                       columns=["#", "산출물", "역할", "규모"])
    st.dataframe(out, width="stretch", hide_index=True,
                 column_config={"역할": st.column_config.TextColumn(width="large")})
    krds.note("네 산출물 모두 왼쪽 내비게이션의 화면으로 연결돼 있다 — "
              "A→<b>태그 성과 스코어보드</b>, B→<b>광고 카드</b>, "
              "C→<b>리스크 경보</b>, D→<b>유통 갭</b>. "
              "여기부터는 <b>설명이 아니라 실제 데이터</b>다.")

    krds.section("솔직한 한계 — 먼저 말하는 것")
    for k, v in story.LIMITS:
        with st.expander(k):
            st.markdown(v, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════ Ⅳ-2. 재고 진단
elif PAGE == "overview":
    krds.page_header(
        "재고 진단", eyebrow="Ⅳ. 시스템 ③ · 운영 화면",
        desc="지금 우리가 가진 광고 재고가 <b>어떤 모양</b>인지, "
             "그리고 기존 분류축이 왜 쓸 수 없었는지를 한 화면에서 본다.",
        meta=[("광고", f"{len(B):,}건"), ("스냅샷", SNAPSHOT),
              ("데이터 소스", "BigQuery" if SOURCE == "BIGQUERY" else "로컬 파케이")])

    krds.cards([
        {"label": "전체 광고", "value": f"{len(B):,}", "unit": "건",
         "tone": "primary", "sub": "클릭이 1건 이상 발생한 광고"},
        {"label": "콜드스타트(학습 불가)", "value": f"{int(B['is_coldstart'].sum()):,}",
         "unit": "건", "tone": "warning",
         "sub": f"전체의 {B['is_coldstart'].mean():.0%} · 클릭이 적어 성과로 판단할 수 없다. "
                "<b>이들에게 점수를 주는 것이 이 시스템의 목적</b>이다."},
        {"label": "전체 CVR", "value": f"{B['conversions'].sum() / B['clicks'].sum():.1%}",
         "tone": "success", "sub": "어뷰징 전처리 후 기준"},
        {"label": "총 매출", "value": f"₩{B['revenue'].sum():,.0f}",
         "tone": "secondary", "sub": "관측 기간 합계"},
    ])

    krds.section("분류축 비교 — 기존 vs 신규",
                 "최빈값 점유율이 낮을수록 ‘광고를 구분하는 능력’이 크다.")
    old = pd.DataFrame({
        "분류축": ["기존 ads_category", "기존 ads_type", "신규 category_l1", "신규 action_type"],
        "값 개수": [B["ads_category"].nunique(), B["ads_type"].nunique(),
                    B["category_l1"].nunique(), B["action_type"].nunique()],
        "최빈값 점유율": [B["ads_category"].value_counts(normalize=True).iloc[0],
                          B["ads_type"].value_counts(normalize=True).iloc[0],
                          B["category_l1"].value_counts(normalize=True).iloc[0],
                          B["action_type"].value_counts(normalize=True).iloc[0]]})
    old["최빈값 점유율"] = old["최빈값 점유율"].map("{:.1%}".format)
    st.dataframe(old, width="stretch", hide_index=True)
    krds.note("기존 축은 한 값에 90% 가까이 몰려 있어 세그먼트 분석이 불가능했다. "
              "<code>ads_category</code> 는 13개 코드 중 하나가 88.9%, "
              "<code>ads_type</code> 은 코드 3(참여형) 하나가 94.2%를 차지한다. "
              "<b>이게 가설 C3 이 기각된 이유</b>이자 이 시스템이 존재하는 이유다.")

    krds.section("대분류별 재고 구성")
    l1 = (B.groupby("category_l1")
            .agg(광고수=("ads_idx", "size"), 클릭=("clicks", "sum"),
                 전환=("conversions", "sum"), 매출=("revenue", "sum")))
    l1["CVR"] = l1["전환"] / l1["클릭"]
    st.bar_chart(l1["광고수"].sort_values(ascending=False), color=krds.C["primary50"])
    st.dataframe(l1.sort_values("클릭", ascending=False)
                 .style.format({"CVR": "{:.1%}", "매출": "₩{:,.0f}",
                                "클릭": "{:,}", "전환": "{:,}", "광고수": "{:,}"}),
                 width="stretch")


# ══════════════════════════════════════════════════════════ Ⅳ-3. 성과 스코어보드
elif PAGE == "scoreboard":
    krds.page_header(
        "태그 성과 스코어보드", eyebrow="Ⅳ. 시스템 ③ · 산출물 A",
        desc="15개 태그 축 중 하나를 골라, 그 축의 <b>값별 실제 성과</b>를 비교한다. "
             "<b>팀원 2의 추천 시스템이 아이템 feature 로 받아 가는 것이 바로 이 태그</b>다.",
        meta=[("태그 축", f"{A['tag_axis'].nunique()}개"),
              ("태그 값", f"{len(A):,}개"), ("스냅샷", SNAPSHOT)])

    axes = sorted(A["tag_axis"].unique())
    ax = st.selectbox("축 선택", axes,
                      index=axes.index("action_type") if "action_type" in axes else 0)
    sub = A[A["tag_axis"] == ax].sort_values("cvr_shrunk", ascending=False)

    top = sub.iloc[0] if len(sub) else None
    bot = sub.iloc[-1] if len(sub) else None
    if top is not None and bot is not None and len(sub) > 1:
        krds.cards([
            {"label": "가장 잘 전환되는 값", "value": str(top["tag_value"]),
             "tone": "success", "sub": f"보정 CVR {top['cvr_shrunk']:.1%} · "
                                       f"광고 {int(top['ads_cnt']):,}건"},
            {"label": "가장 안 되는 값", "value": str(bot["tag_value"]),
             "tone": "danger", "sub": f"보정 CVR {bot['cvr_shrunk']:.1%} · "
                                      f"광고 {int(bot['ads_cnt']):,}건"},
            {"label": "최고−최저 격차",
             "value": f"{top['cvr_shrunk'] - bot['cvr_shrunk']:+.1%}", "tone": "primary",
             "sub": "이 격차가 클수록 그 축이 성과를 잘 가른다"},
        ], cols=3)

    krds.section(f"‘{ax}’ 축의 값별 보정 CVR", level=3)
    st.bar_chart(sub.set_index("tag_value")["cvr_shrunk"], color=krds.C["primary50"])
    krds.note("<code>cvr_shrunk</code> = 소표본 보정 CVR. 클릭이 적은 태그값이 순위를 흔들지 않도록 "
              "전체 평균 쪽으로 당긴 값이다(α=100). "
              "<code>ci_low</code>~<code>ci_high</code> 가 넓으면 표본이 적다는 뜻이니 그대로 믿지 말 것.")
    st.dataframe(
        sub[["tag_value", "ads_cnt", "n_reliable", "clicks", "conversions",
             "cvr", "cvr_shrunk", "ci_low", "ci_high", "revenue", "margin_rate"]]
        .style.format({"cvr": "{:.1%}", "cvr_shrunk": "{:.1%}", "ci_low": "{:.1%}",
                       "ci_high": "{:.1%}", "margin_rate": "{:.1%}",
                       "clicks": "{:,}", "conversions": "{:,}", "revenue": "₩{:,.0f}"}),
        width="stretch", hide_index=True)


# ══════════════════════════════════════════════════════════ Ⅳ-4. 마찰 분석
elif PAGE == "friction":
    krds.page_header(
        "마찰 분석", eyebrow="Ⅳ. 시스템 ③ · 핵심",
        desc="이 시스템이 운영진에게 <b>말로 전달할 수 있는</b> 결과물이다. "
             "‘무엇이 전환을 깎는가’를 조건 단위로 보여준다. "
             "<b>가설 C1·C2 가 지지된 자리</b>이기도 하다.",
        meta=[("스냅샷", SNAPSHOT), ("기준", "클릭가중 CVR 차이")])

    if LIFT.empty:
        krds.alert("warning", "tag_effect.parquet 이 없습니다",
                   "<code>/usr/bin/python3 scripts/run_pipeline.py</code> 로 산출물을 만드세요.")
    else:
        fr = LIFT[LIFT["axis"] == "friction_flags"].sort_values("lift")
        worst = fr.head(3)
        if len(worst):
            krds.section("전환을 가장 크게 깎는 조건 3가지", level=3)
            krds.rows([(str(r.flag), f"{r.lift:+.1%}",
                        f"해당 광고 {int(r.n_with):,}건") for r in worst.itertuples()])

        krds.section("조건별 리프트")
        krds.note("리프트 = (해당 조건을 가진 광고의 클릭가중 CVR) − (없는 광고의 CVR). "
                  "<b>음수일수록 그 조건이 전환을 깎는다.</b> "
                  "이건 상관이지 인과가 아니다 — A/B 테스트로만 인과를 말할 수 있다.")
        st.bar_chart(fr.set_index("flag")["lift"], color=krds.C["danger50"])
        show = LIFT.sort_values("lift")[
            ["axis", "flag", "n_with", "clicks_with", "cvr_with", "cvr_without",
             "lift", "ci_low", "ci_high", "revenue_with"]]
        st.dataframe(show.style.format({
            "cvr_with": "{:.1%}", "cvr_without": "{:.1%}", "lift": "{:+.1%}",
            "ci_low": "{:+.1%}", "ci_high": "{:+.1%}", "n_with": "{:,}",
            "clicks_with": "{:,}", "revenue_with": "₩{:,.0f}"}),
            width="stretch", hide_index=True)

    krds.section("마찰 개수와 CVR")
    fc = (B.groupby("friction_count")
            .agg(광고수=("ads_idx", "size"), 클릭=("clicks", "sum"),
                 전환=("conversions", "sum")))
    fc["CVR"] = fc["전환"] / fc["클릭"]
    st.line_chart(fc["CVR"], color=krds.C["primary50"])
    krds.note("가로축은 한 광고가 가진 마찰 조건의 개수다. "
              "우하향한다면 ‘마찰이 쌓일수록 전환이 떨어진다’는 관계가 재고 전체에서 관측된다는 뜻이다.")
    st.dataframe(fc.style.format({"CVR": "{:.1%}", "클릭": "{:,}",
                                  "전환": "{:,}", "광고수": "{:,}"}),
                 width="stretch")

    krds.alert("gray", "“몇 개냐”가 아니라 “어떤 것이냐”가 전부였다",
               "처음엔 마찰을 전부 세어 상관을 봤는데 거의 안 보였다(ρ −0.07 · <b>게이트 실패</b>). "
               "알고 보니 <code>신규유저한정</code>(44%)·<code>기한내참여필수</code>(51%)·"
               "<code>재참여불가</code>(35%)는 거의 모든 광고에 붙는 <b>상투 문구</b>였다. "
               "이 셋을 빼고 다시 세니 상관이 <b>−0.43</b> 으로 드러났다. "
               "실패한 게이트는 성공으로 포장하지 않고 원인과 함께 리포트에 남겼다.")


# ══════════════════════════════════════════════════════════ Ⅳ-5. 광고 카드
elif PAGE == "cards":
    krds.page_header(
        "광고 카드", eyebrow="Ⅳ. 시스템 ③ · 산출물 B",
        desc="광고 하나를 지목해 <b>태그·기대 성과·마찰·판단 근거</b>를 한 줄로 확인한다.",
        meta=[("전체", f"{len(B):,}건"),
              ("콜드스타트", f"{int(B['is_coldstart'].sum()):,}건"), ("스냅샷", SNAPSHOT)])

    q = st.text_input("광고명 검색", "")
    c1, c2, c3 = st.columns([2, 2, 1])
    g = c1.multiselect("등급", sorted(B["grade"].unique()))
    l1s = c2.multiselect("대분류", sorted(B["category_l1"].unique()))
    only_cold = c3.checkbox("콜드스타트만")

    v = B
    if q:
        v = v[v["ads_name"].str.contains(q, case=False, na=False)]
    if g:
        v = v[v["grade"].isin(g)]
    if l1s:
        v = v[v["category_l1"].isin(l1s)]
    if only_cold:
        v = v[v["is_coldstart"]]

    dist = v["grade"].value_counts()
    krds.cards([{"label": f"{gr} 등급", "value": f"{int(dist.get(gr, 0)):,}", "unit": "건",
                 "tone": krds.GRADE_TONE.get(gr, "gray")}
                for gr in ["S", "A", "B", "C", "D"]], cols=5)

    krds.note(f"검색 결과 <b>{len(v):,}건</b> (표에는 클릭 상위 500건만 표시). "
              "<code>expected_cvr</code> 은 <b>광고 제목+설명문</b>만으로 예측한 값이라 "
              "성과 이력이 0인 광고에도 채워진다 "
              "(LLM 태그 15축 + 텍스트 TF-IDF/SVD 100 → LightGBM). "
              "<code>gap</code> = 실제 − 기대.")
    cols = ["ads_idx", "ads_name", "grade", "category_l1", "category_l2", "action_type",
            "difficulty", "friction_count", "risk_level", "clicks", "cvr",
            "expected_cvr", "expected_cvr_sd", "gap", "revenue", "evidence_phrase"]
    st.dataframe(v[cols].sort_values("clicks", ascending=False).head(500)
                 .style.format({"cvr": "{:.1%}", "expected_cvr": "{:.1%}",
                                "expected_cvr_sd": "{:.3f}", "gap": "{:+.1%}",
                                "clicks": "{:,}", "revenue": "₩{:,.0f}"}),
                 width="stretch", hide_index=True, height=560)


# ══════════════════════════════════════════════════════════ Ⅳ-6. 리스크 경보
elif PAGE == "risk":
    krds.page_header(
        "리스크 경보", eyebrow="Ⅳ. 시스템 ③ · 산출물 C",
        desc="기대보다 크게 미달하거나, 위험 신호가 잡힌 광고를 심각도 순으로 모았다. "
             "<b>경보는 ‘차단’이 아니라 ‘확인 요청’</b>이다.",
        meta=[("경보 전체", f"{len(Cc):,}건"), ("스냅샷", SNAPSHOT)])

    if Cc.empty:
        krds.alert("success", "경보 없음", "현재 심각도 기준을 넘는 광고가 없습니다.")
    else:
        sev = st.multiselect("심각도(severity)", [3, 2, 1], default=[3, 2])
        v = Cc[Cc["severity"].isin(sev)] if sev else Cc

        krds.cards([
            {"label": "경보 광고", "value": f"{len(v):,}", "unit": "건", "tone": "danger"},
            {"label": "경보 클릭 비중",
             "value": f"{v['clicks'].sum() / B['clicks'].sum():.1%}", "tone": "warning",
             "sub": "전체 클릭 대비"},
            {"label": "경보 매출", "value": f"₩{v['revenue'].sum():,.0f}",
             "tone": "secondary", "sub": "해당 광고들의 매출 합계"},
        ], cols=3)

        krds.section("경보 목록", "상위 30건만 표시한다. 펼치면 판단 근거가 나온다.")
        for r in v.head(30).itertuples():
            with st.expander(f"[심각도 {r.severity}] {r.ads_name}  ·  클릭 {r.clicks:,}"):
                badges = krds.badge(f"심각도 {r.severity}",
                                    krds.SEVERITY_TONE.get(int(r.severity), "gray"), square=True)
                for f in list(r.friction_flags):
                    badges += " " + krds.badge(str(f), "warning", square=True)
                for f in list(r.risk_flags):
                    badges += " " + krds.badge(str(f), "danger", square=True)
                st.markdown(badges, unsafe_allow_html=True)
                st.write(r.alert_reason)
                st.json({"expected_cvr": round(float(r.expected_cvr), 4),
                         "actual_cvr": None if pd.isna(r.cvr) else round(float(r.cvr), 4)})


# ══════════════════════════════════════════════════════════ Ⅳ-7. 유통 갭
elif PAGE == "gap":
    krds.page_header(
        "유통 갭", eyebrow="Ⅳ. 시스템 ③ · 산출물 D",
        desc="매체별로 <b>평균보다 잘 소화하는 태그 조합</b>을 찾고, "
             "그 조합인데 아직 그 매체에 안 나간 광고를 후보로 제안한다. "
             "<b>“배분이 품질과 무관하다(−0.17)”는 신호 ③에 대한 직접적인 실행 도구</b>다.",
        meta=[("후보 조합", f"{len(D):,}건"), ("스냅샷", SNAPSHOT)])

    if D.empty:
        krds.alert("information", "유통 갭 후보 없음",
                   "매체별 리프트가 기준을 넘는 조합이 없습니다.")
    else:
        mda = st.selectbox("매체 선택", sorted(D["mda_idx"].unique()))
        v = D[D["mda_idx"] == mda].sort_values("lift", ascending=False)
        krds.note("이 매체가 평균보다 잘 소화하는 태그 조합인데, "
                  "아직 이 매체에 노출된 적 없는 광고 후보다. "
                  "<b>관측된 상관에 기반한 제안이며, 실제 배정 전에는 소규모 테스트를 권한다.</b>")
        krds.section(f"매체 {mda} — 리프트 상위 조합", level=3)
        for r in v.itertuples():
            with st.expander(
                    f"{r.category_l1} × {r.action_type} — 매체 CVR {r.media_cvr:.1%} "
                    f"vs 전체 {r.overall_cvr:.1%} (리프트 {r.lift:+.1%})"):
                st.markdown(
                    krds.badge(f"리프트 {r.lift:+.1%}", "success", square=True) + " "
                    + krds.badge(f"후보 {len(r.candidate_top10)}건", "primary", square=True) + " "
                    + krds.badge(f"평균 기대 CVR {r.cand_mean_expected_cvr:.1%}",
                                 "gray", square=True),
                    unsafe_allow_html=True)
                st.dataframe(pd.DataFrame({"ads_idx": r.candidate_top10,
                                           "ads_name": r.candidate_top10_names}),
                             width="stretch", hide_index=True)


# ══════════════════════════════════════════════════════════ Ⅳ-8. 신규 광고 진단
elif PAGE == "newads":
    krds.page_header(
        "신규 광고 진단", eyebrow="Ⅳ. 시스템 ③ · 콜드스타트",
        desc="어제 새로 들어온 광고를 <b>성과 이력 없이</b> 제목·설명문만으로 등급화한 결과다. "
             "<b>이 시스템이 존재하는 이유가 이 화면 하나</b>다.",
        meta=[("스냅샷", SNAPSHOT), ("판단 근거", "텍스트 only")])

    new = B[B["ads_idx"] >= DEMO_IDX_MIN].copy()

    if new.empty:
        krds.alert("information", "신규 광고가 없습니다",
                   "<code>scripts/demo_new_ads.py --load</code> 로 시연용 데이터를 넣고 "
                   "Airflow t06~t09 를 돌리면 여기에 나타납니다.")
    else:
        krds.alert("warning", f"이 {len(new)}건은 시연용 합성 데이터입니다 (실제 운영 로그 아님)",
                   "<code>ads_idx ≥ 990000</code> · 광고코드 <code>DEMO_</code> 로 구분되며, "
                   "모델 <b>학습에는 쓰이지 않습니다</b>(예측만 받습니다).")

        risky = int((new["risk_level"] == "높음").sum())
        krds.cards([
            {"label": "신규 광고", "value": f"{len(new):,}", "unit": "건", "tone": "primary"},
            {"label": "전부 콜드스타트", "value": f"{int(new['is_coldstart'].sum()):,}",
             "unit": "건", "tone": "warning", "sub": "클릭 50건 미만 — 성과로 판단 불가"},
            {"label": "평균 기대 CVR", "value": f"{new['expected_cvr'].mean():.1%}",
             "tone": "information", "sub": "절대값이 아니라 순위로 볼 것"},
            {"label": "리스크 ‘높음’", "value": f"{risky}", "unit": "건",
             "tone": "danger" if risky else "success",
             "sub": "확인 필요" if risky else "해당 없음"},
        ])

        krds.section("등급별 분포 — 텍스트만 보고 매긴 순위")
        gd = (new.groupby("grade").agg(광고수=("ads_idx", "size"),
                                       평균기대CVR=("expected_cvr", "mean"),
                                       평균마찰=("friction_count", "mean"))
              .reindex(["S", "A", "B", "C", "D"]).dropna(how="all"))
        st.dataframe(gd.style.format({"평균기대CVR": "{:.1%}", "평균마찰": "{:.1f}"}),
                     width="stretch")

        krds.section("광고별 진단")
        show = new[["ads_idx", "ads_name", "category_l1", "action_type", "clicks",
                    "expected_cvr", "grade", "friction_count", "risk_level",
                    "evidence_phrase"]].sort_values("expected_cvr", ascending=False)
        st.dataframe(
            show.rename(columns={
                "ads_idx": "광고ID", "ads_name": "광고명", "category_l1": "분류",
                "action_type": "요구행동", "clicks": "클릭", "expected_cvr": "기대CVR",
                "grade": "등급", "friction_count": "마찰수", "risk_level": "리스크",
                "evidence_phrase": "판단근거"})
              .style.format({"기대CVR": "{:.1%}"}),
            width="stretch", hide_index=True, height=420)

        krds.section("운영 액션 제안")
        cA, cB = st.columns(2)
        with cA:
            krds.section("노출을 늘릴 후보", level=3)
            krds.rows([(f"{r.ads_name}", f"{r.expected_cvr:.1%}",
                        f"마찰 {r.friction_count}개") for r in show.head(3).itertuples()])
        with cB:
            krds.section("먼저 검토가 필요한 광고", level=3)
            krds.rows([(f"{r.ads_name}", f"{r.expected_cvr:.1%}",
                        f"마찰 {r.friction_count}개 · {r.risk_level}")
                       for r in show.tail(3).itertuples()])

        krds.note("성과 데이터가 0인 상태에서 제목·설명문만으로 매긴 등급이다. "
                  "실제 성과가 쌓이면 다음 배치에서 자동으로 갱신된다.")

        with st.expander("⚠️ 이 등급을 읽을 때 주의할 점 (꼭 읽어주세요)"):
            real_cold = B[(B["is_coldstart"]) & (B["ads_idx"] < DEMO_IDX_MIN)]
            st.markdown(f"""
**절대값이 아니라 순위로 보세요.**

이 신규 광고들의 평균 기대 CVR은 **{new['expected_cvr'].mean():.1%}** 인데,
기존 콜드스타트 광고 {len(real_cold):,}건의 평균은 **{real_cold['expected_cvr'].mean():.1%}** 입니다.
**모델은 처음 보는 문체의 광고를 체계적으로 낮게 예측합니다.**

이유는 예측에 쓰는 텍스트 피처(TF-IDF)가 **학습 코퍼스의 어휘 패턴**을 학습했기 때문입니다.
기존 광고들이 공유하는 상투적 표현을 새 광고가 갖고 있지 않으면 낯선 입력으로 취급됩니다.
이건 `docs/EXPERIMENTS.md` 에 기록된 **공변량 이동(AUC 0.911)** 한계가 실제로 드러난 것입니다.

**그래서 이렇게 쓰세요**
- ✅ "이 20건 중 어디에 먼저 노출을 몰아줄까" → **순위는 신뢰할 수 있습니다**
- ❌ "이 광고의 CVR이 27%일 것이다" → **절대값은 보수적으로 치우쳐 있습니다**
- ✅ 첫 성과가 쌓이면(클릭 50건 이상) 실측 기반으로 다시 판단하세요
""")


# ══════════════════════════════════════════════════════════ Ⅳ-9. 검증 결과
elif PAGE == "validation":
    krds.page_header(
        "검증 결과", eyebrow="Ⅳ. 시스템 ③ · 신뢰도",
        desc="이 시스템의 숫자를 믿어도 되는 근거와, <b>믿으면 안 되는 지점</b>을 함께 적었다.",
        meta=[("태깅 모델", MODEL_VER), ("스냅샷", SNAPSHOT)])

    krds.alert("information", "검문소(게이트)를 미리 만들어 둔 이유",
               "분석이 실패하는 흔한 방식은 <b>중간에 틀렸는데 모르고 끝까지 가는 것</b>이다. "
               "그래서 기준을 미리 숫자로 정해두고 못 넘으면 파이프라인이 자동으로 멈춘다"
               "(총 99개 검사). 실제로 실패한 게이트도 성공으로 포장하지 않고 "
               "원인과 함께 리포트에 남겼다 — <b>마찰 분석</b> 화면 하단 참조.")

    if not EV:
        krds.alert("warning", "model_eval.json 이 없습니다",
                   "<code>/usr/bin/python3 scripts/run_pipeline.py</code> 를 실행하세요.")
    else:
        krds.section("Gate G2 — 태그가 기존 분류보다 CVR을 잘 설명하는가")
        M = EV["models"]
        t = pd.DataFrame([
            {"실험": k, "설명": d, "feature 수": M[k]["n_features"],
             "R² (5-fold)": M[k]["r2"], "MAE": M[k]["mae"]}
            for k, d in [("B0", "기존 ads_category+ads_type"),
                         ("B1", "기존 + 운영변수"),
                         ("T", "신규 태그 15축"),
                         ("T+", "신규 태그 + 운영변수")]])
        st.dataframe(t.style.format({"R² (5-fold)": "{:+.4f}", "MAE": "{:.4f}"}),
                     width="stretch", hide_index=True)
        lo, hi = EV["r2_diff_ci"]
        krds.cards([
            {"label": "R²(태그) − R²(기존)", "value": f"{EV['r2_diff_T_B0']:+.4f}",
             "tone": "primary", "sub": f"95% 신뢰구간 [{lo:+.4f}, {hi:+.4f}]"},
            {"label": "마찰 개수 ↔ CVR (Spearman ρ)",
             "value": f"{EV['spearman_friction']['rho']:+.4f}", "tone": "danger",
             "sub": f"p = {EV['spearman_friction']['p']:.2e} · "
                    "음수일수록 ‘마찰이 많을수록 전환이 떨어진다’가 강하다"},
        ], cols=2)

        krds.section("축별 설명력 η²", "각 태그 축이 CVR 분산을 얼마나 설명하는가.")
        st.bar_chart(pd.Series(EV["eta_squared"]).sort_values(ascending=False),
                     color=krds.C["graphic50"])

        krds.section("그룹 간 차이 검정 (Kruskal–Wallis)", level=3)
        st.dataframe(pd.Series(EV["kruskal_p"]).to_frame("p-value")
                     .style.format("{:.2e}"), width="stretch")

        krds.section("피처 구성 비교 — 진짜 홀드아웃")
        krds.note("학습에 한 번도 쓰이지 않은 신생 광고(클릭 10~49, 브랜드도 비중복)로 평가했다. "
                  "스코어카드가 실제 운영에서 하는 일과 같은 조건이다.")
        fc = load("feature_comparison")
        if fc.empty:
            krds.alert("warning", "feature_comparison.parquet 이 없습니다",
                       "<code>/usr/bin/python3 scripts/x_finalize.py</code> 를 실행하세요.")
        else:
            st.dataframe(
                fc[["variant", "r2", "spearman", "grade_D", "grade_S", "S_minus_D"]]
                .rename(columns={"variant": "피처 구성", "spearman": "순위정확도(Spearman)",
                                 "grade_D": "D등급 실제CVR", "grade_S": "S등급 실제CVR",
                                 "S_minus_D": "S−D 격차"})
                .style.format({"r2": "{:+.4f}", "순위정확도(Spearman)": "{:+.4f}",
                               "D등급 실제CVR": "{:.1%}", "S등급 실제CVR": "{:.1%}",
                               "S−D 격차": "{:+.1%}"}),
                width="stretch", hide_index=True)
            krds.alert("information", "LLM 태그만으로는 부족하다 — 실험으로 확인됐다",
                       "예측에는 태그 + 텍스트 피처를 함께 쓰고, "
                       "태그는 진단·경보의 ‘언어’로 쓴다. "
                       "근거는 <code>docs/EXPERIMENTS.md</code> (실험 47건).")

        mc = load("model_comparison")
        if not mc.empty:
            krds.section("모델 비교 (같은 피처·같은 분할·같은 시드)")
            krds.note("<code>0_평균예측</code> 은 아무것도 학습하지 않는 기준선이다. "
                      "<b>이걸 못 이기면 모델이 무의미하다.</b>")
            st.dataframe(mc.style.format({"r2": "{:+.4f}", "mae": "{:.4f}"}),
                         width="stretch", hide_index=True)


# ══════════════════════════════════════════════════════════ Ⅴ. 마무리
elif PAGE == "closing":
    krds.page_header(
        "기술 스택 · 예상 반론",
        eyebrow="Ⅴ. 마무리",
        desc="“분석”이 아니라 “운영”이 되도록 고른 도구들과, "
             "발표 전에 <b>스스로 던져본 반론</b>을 그대로 적었다.",
        meta=[("시스템", "3개"), ("문서 기준", story.UPDATED)])

    krds.section("기술 스택 — 분석이 아니라 ‘운영’되도록")
    st.dataframe(pd.DataFrame(story.STACK, columns=["구성", "선택", "이유"]),
                 width="stretch", hide_index=True,
                 column_config={"이유": st.column_config.TextColumn(width="large")})
    krds.note("한 번의 분석으로 끝나는 문제가 아니었기 때문이다 — "
              "신규 광고는 하루 254개, 어뷰징은 상시. "
              "<b>Airflow 일배치로 매일 자동 갱신되고, 이 대시보드가 그 결과를 읽는다.</b>")

    krds.section("예상 반론과 방어", "약점을 감추지 않는 편이 결국 설득력이 높다.")
    for q, a in story.REBUTTALS:
        with st.expander(f"“{q}”"):
            st.markdown(a, unsafe_allow_html=True)

    krds.section("남은 일")
    krds.rows([
        ("시스템 ① 어뷰징 탐지", "완료", "팀원 1 — 2026-08-25 자료 수령·검증·반영 (Ⅱ 화면)"),
        ("시스템 ② 개인화 추천", "자료 대기", "팀원 2 — 모델 구조·오프라인 평가·추천 예시"),
        ("시스템 ③ 광고 선별·진단", "완료", "BigQuery 적재 · Airflow 일배치 · 대시보드 운영 중"),
    ], ranked=False)

    krds.section("수치 출처", f"모든 수치의 원본은 프로젝트 루트 {story.DOC} 이다.")
    st.dataframe(pd.DataFrame(story.SOURCES, columns=["수치", "출처"]),
                 width="stretch", hide_index=True,
                 column_config={"수치": st.column_config.TextColumn(width="large"),
                                "출처": st.column_config.TextColumn(width="large")})


# ══════════════════════════════════════════════════════════ 공통 푸터
krds.footer([
    "<b>리워드 광고 플랫폼 진단</b> · 데이터 스프린트 통합 대시보드 · 내부용",
    "시스템 ① 어뷰징 탐지(팀원1) <span class=\"k-fsep\">|</span> "
    "② 개인화 추천(팀원2) <span class=\"k-fsep\">|</span> ③ 광고 선별·진단(본인)",
    f"데이터 스냅샷 {krds.e(SNAPSHOT)}"
    f'<span class="k-fsep">|</span>태깅 모델 {krds.e(MODEL_VER)}'
    f'<span class="k-fsep">|</span>소스 {"BigQuery" if SOURCE == "BIGQUERY" else "로컬 파케이"}',
    "CVR 은 <b>어뷰징 전처리 후</b> 기준입니다. 외부에 인용할 때 반드시 병기하세요.",
    "화면 디자인은 KRDS(대한민국 정부 디자인 시스템) v1.0.0 의 컬러·타이포·컴포넌트 규칙을 "
    "차용했습니다. 정부 서비스가 아니며 정부상징·masthead 는 사용하지 않았습니다.",
])
