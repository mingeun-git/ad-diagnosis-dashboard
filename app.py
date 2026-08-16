"""광고 선별(진단) 시스템 — 운영진 대시보드.

디자인
------
KRDS(대한민국 정부 디자인 시스템) v1.0.0 을 적용했다.
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

st.set_page_config(page_title="광고 선별(진단) 시스템",
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

if B.empty:
    krds.masthead("<b>리워드 광고 플랫폼</b> · 광고 진단 시스템")
    krds.alert("danger", "산출물이 없습니다",
               "먼저 <code>/usr/bin/python3 scripts/run_pipeline.py</code> 를 실행하세요.")
    st.stop()

MOCK = str(B.get("model_version", pd.Series(["?"])).iloc[0]).upper() == "MOCK" \
    if "model_version" in B.columns else False

SNAPSHOT = str(B["snapshot_date"].max()) if "snapshot_date" in B else "-"
MODEL_VER = str(EV.get("model_version", "?"))


# ══════════════════════════════════════════════════════════ 사이드 내비게이션
NAV: list[tuple[str, list[tuple[str, str]]]] = [
    ("진단 요약", [
        ("overview", "재고 진단"),
    ]),
    ("태그 성과 분석", [
        ("scoreboard", "성과 스코어보드"),
        ("friction", "마찰 분석"),
        ("gap", "유통 갭"),
    ]),
    ("광고 단위 조회", [
        ("cards", "광고 카드"),
        ("risk", "리스크 경보"),
        ("newads", "신규 광고"),
    ]),
    ("시스템 신뢰도", [
        ("validation", "검증 결과"),
    ]),
]

if "page" not in st.session_state:
    st.session_state.page = "overview"

with st.sidebar:
    krds.nav_brand("광고 선별(진단) 시스템", "운영진 전용")
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
        ("광고 수", f"{len(B):,}", ""),
    ], ranked=False)

PAGE = st.session_state.page

# ══════════════════════════════════════════════════════════ 공통 헤더
krds.masthead("<b>리워드 광고 플랫폼</b> · 광고 진단 시스템",
              f"데이터 스냅샷 {SNAPSHOT}")

if MOCK:
    krds.alert("danger", "MOCK 데이터입니다",
               "태그 내용에 의미가 없습니다 — 배관(파이프라인) 검증용 실행 결과입니다.")


# ══════════════════════════════════════════════════════════ ① 재고 진단
if PAGE == "overview":
    krds.page_header(
        "재고 진단", eyebrow="진단 요약",
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
              "<code>ads_type</code> 은 설치형 하나가 94.2%를 차지한다.")

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


# ══════════════════════════════════════════════════════════ ② 성과 스코어보드
elif PAGE == "scoreboard":
    krds.page_header(
        "성과 스코어보드", eyebrow="태그 성과 분석",
        desc="15개 태그 축 중 하나를 골라, 그 축의 <b>값별 실제 성과</b>를 비교한다.",
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


# ══════════════════════════════════════════════════════════ ③ 마찰 분석
elif PAGE == "friction":
    krds.page_header(
        "마찰 분석", eyebrow="태그 성과 분석 · 핵심",
        desc="이 시스템이 운영진에게 <b>말로 전달할 수 있는</b> 유일한 결과물이다. "
             "‘무엇이 전환을 깎는가’를 조건 단위로 보여준다.",
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


# ══════════════════════════════════════════════════════════ ④ 광고 카드
elif PAGE == "cards":
    krds.page_header(
        "광고 카드", eyebrow="광고 단위 조회",
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


# ══════════════════════════════════════════════════════════ ⑤ 리스크 경보
elif PAGE == "risk":
    krds.page_header(
        "리스크 경보", eyebrow="광고 단위 조회",
        desc="기대보다 크게 미달하거나, 위험 신호가 잡힌 광고를 심각도 순으로 모았다.",
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


# ══════════════════════════════════════════════════════════ ⑥ 유통 갭
elif PAGE == "gap":
    krds.page_header(
        "유통 갭", eyebrow="태그 성과 분석",
        desc="매체별로 <b>평균보다 잘 소화하는 태그 조합</b>을 찾고, "
             "그 조합인데 아직 그 매체에 안 나간 광고를 후보로 제안한다.",
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


# ══════════════════════════════════════════════════════════ ⑦ 검증 결과
elif PAGE == "validation":
    krds.page_header(
        "검증 결과", eyebrow="시스템 신뢰도",
        desc="이 시스템의 숫자를 믿어도 되는 근거와, <b>믿으면 안 되는 지점</b>을 함께 적었다.",
        meta=[("태깅 모델", MODEL_VER), ("스냅샷", SNAPSHOT)])

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
                       "근거는 <code>docs/EXPERIMENTS.md</code> (실험 43건).")

        mc = load("model_comparison")
        if not mc.empty:
            krds.section("모델 비교 (같은 피처·같은 분할·같은 시드)")
            krds.note("<code>0_평균예측</code> 은 아무것도 학습하지 않는 기준선이다. "
                      "<b>이걸 못 이기면 모델이 무의미하다.</b>")
            st.dataframe(mc.style.format({"r2": "{:+.4f}", "mae": "{:.4f}"}),
                         width="stretch", hide_index=True)


# ══════════════════════════════════════════════════════════ ⑧ 신규 광고
elif PAGE == "newads":
    krds.page_header(
        "신규 광고", eyebrow="광고 단위 조회",
        desc="어제 새로 들어온 광고를 <b>성과 이력 없이</b> 제목·설명문만으로 등급화한 결과다.",
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


# ══════════════════════════════════════════════════════════ 공통 푸터
krds.footer([
    "<b>광고 선별(진단) 시스템</b> · 데이터 스프린트 파트③ · 운영진 내부용",
    f"데이터 스냅샷 {krds.e(SNAPSHOT)}"
    f'<span class="k-fsep">|</span>태깅 모델 {krds.e(MODEL_VER)}'
    f'<span class="k-fsep">|</span>소스 {"BigQuery" if SOURCE == "BIGQUERY" else "로컬 파케이"}',
    "CVR 은 <b>어뷰징 전처리 후</b> 기준입니다. 외부에 인용할 때 반드시 병기하세요.",
    "화면 디자인은 KRDS(대한민국 정부 디자인 시스템) v1.0.0 의 컬러·타이포·컴포넌트 규칙을 "
    "차용했습니다. 정부 서비스가 아니며 정부상징·masthead 는 사용하지 않았습니다.",
])
