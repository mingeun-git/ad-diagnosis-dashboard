"""KRDS(대한민국 정부 디자인 시스템) v1.0.0 을 Streamlit 에 입히는 테마 모듈.

왜 이 파일이 따로 있나
----------------------
Streamlit 은 기본 스킨이 강해서, 앱 코드 안에 CSS 를 섞어 넣으면
"데이터 로직"과 "생김새"가 뒤엉켜 나중에 아무도 못 고친다.
그래서 **디자인 시스템 적용은 전부 이 파일 하나로 격리**한다.
`app.py` 는 `krds.setup()` 만 부르고, 나머지는 여기 정의된 컴포넌트만 쓴다.

디자인 토큰 출처 (2026-08-16 확보)
-----------------------------------
- 토큰 원본 : https://github.com/KRDS-uiux/krds-uiux
              `resources/css/token/krds_tokens.css` (2024-12-09 생성본, 790줄)
              → 같은 폴더 `krds_tokens_reference.css` 에 원본 그대로 보관해 둠
- 서체      : PretendardGOV Regular/Medium/Bold (같은 저장소 `resources/fonts/`)
              jsDelivr CDN 으로 로드. 없는 글자는 Pretendard 로 폴백한다.
- 가이드    : https://www.krds.go.kr  ·  Figma 커뮤니티 파일 'KRDS_v1.0.0'

⚠️ 지키는 선
------------
KRDS 의 **masthead(정부 누리집 식별 배너)** 와 **정부상징(태극/정부로고)** 은 쓰지 않는다.
이 대시보드는 정부 서비스가 아니므로 그대로 쓰면 사칭이 된다.
컬러·타이포·간격·컴포넌트 형태만 차용하고, 상단 배너는 '내부 운영 시스템' 표기로 바꿨다.

단위 주의
---------
KRDS 원본 CSS 는 `html { font-size: 62.5% }` 를 전제로 `1rem = 10px` 이다.
Streamlit 에서는 그 전제를 만들 수 없으므로, 이 파일에서는 **전부 px 로 환산**해 적었다.
(예: KRDS `--krds-number-4: 0.6rem` → 6px)
"""
from __future__ import annotations

import html as _html
from typing import Iterable, Sequence

import streamlit as st

# ══════════════════════════════════════════════════════════ 1. 디자인 토큰
# krds_tokens.css 의 PRIMITIVE(light) 계열을 그대로 옮긴 것. 값은 손대지 않았다.
C: dict[str, str] = {
    # Primary — 정부 상징 블루
    "primary5": "#ecf2fe", "primary10": "#d8e5fd", "primary20": "#b1cefb",
    "primary30": "#86aff9", "primary40": "#4c87f6", "primary50": "#256ef4",
    "primary60": "#0b50d0", "primary70": "#083891", "primary80": "#052561",
    # Secondary
    "secondary5": "#eef2f7", "secondary10": "#d6e0eb", "secondary50": "#346fb2",
    "secondary70": "#063a74", "secondary80": "#052b57",
    # Gray 13단계
    "gray0": "#ffffff", "gray5": "#f4f5f6", "gray10": "#e6e8ea", "gray20": "#cdd1d5",
    "gray30": "#b1b8be", "gray40": "#8a949e", "gray50": "#6d7882", "gray60": "#58616a",
    "gray70": "#464c53", "gray80": "#33363d", "gray90": "#1e2124", "gray95": "#131416",
    # System — Danger / Warning / Success / Information
    "danger5": "#fdefec", "danger10": "#fcdfd9", "danger50": "#de3412",
    "danger60": "#bd2c0f", "danger70": "#8a240f",
    "warning5": "#fff3db", "warning10": "#ffe0a3", "warning50": "#9e6a00",
    "warning60": "#8a5c00", "warning70": "#614100",
    "success5": "#eaf6ec", "success10": "#d8eedd", "success50": "#228738",
    "success60": "#267337", "success70": "#285d33",
    "information5": "#e7f4fe", "information10": "#d3ebfd", "information50": "#0b78cb",
    "information60": "#096ab3", "information70": "#085691",
    # Point(강조) · Graphic(차트)
    "point5": "#fbeff0", "point10": "#f5d6d9", "point50": "#d63d4a", "point60": "#ab2b36",
    "graphic10": "#e5ecf9", "graphic30": "#98acc5", "graphic50": "#61758f",
    "graphic70": "#39506c", "graphic90": "#223a58",
    # Alpha shadow
    "shadow1": "#0000000d", "shadow2": "#00000014", "shadow3": "#0000001f",
}

# 차트 색 — Streamlit config.toml 의 chartCategoricalColors 와 같은 순서로 맞춰 둔다.
CHART_CATEGORICAL: list[str] = [
    C["primary50"], C["graphic50"], C["information50"], C["point50"],
    C["success50"], C["warning50"], C["secondary50"], C["graphic30"],
    C["primary30"], C["graphic90"],
]

# KRDS 타이포 스케일(PC). 원본 rem(1rem=10px) → px 환산.
FS = {
    "display_s": 36, "heading_xl": 40, "heading_l": 32, "heading_m": 24,
    "heading_s": 19, "heading_xs": 17, "heading_xxs": 15,
    "body_l": 19, "body_m": 17, "body_s": 15, "body_xs": 13,
}

# KRDS radius (원본: xsmall 2px / small 4px / medium 6~8px / large 10px)
RADIUS = {"xs": "2px", "sm": "4px", "md": "6px", "lg": "10px", "max": "999px"}

# 톤(tone) → (배경, 테두리, 글자) 3종 세트. KRDS SEMANTIC 매핑을 따른다.
_TONES = {
    "default":     (C["gray0"],        C["gray20"],        C["gray90"]),
    "primary":     (C["primary5"],     C["primary20"],     C["primary60"]),
    "secondary":   (C["secondary5"],   C["secondary10"],   C["secondary80"]),
    "danger":      (C["danger5"],      C["danger10"],      C["danger60"]),
    "warning":     (C["warning5"],     C["warning10"],     C["warning60"]),
    "success":     (C["success5"],     C["success10"],     C["success60"]),
    "information": (C["information5"], C["information10"], C["information60"]),
    "point":       (C["point5"],       C["point10"],       C["point60"]),
    "gray":        (C["gray5"],        C["gray20"],        C["gray70"]),
}


def tone(name: str) -> tuple[str, str, str]:
    """톤 이름 → (배경색, 테두리색, 글자색)."""
    return _TONES.get(name, _TONES["default"])


def e(x) -> str:
    """HTML 이스케이프. 광고명 등 **데이터에서 온 문자열은 반드시 이걸 통과**시킨다."""
    return _html.escape(str(x), quote=True)


# ══════════════════════════════════════════════════════════ 2. CSS
_FONT_CDN = "https://cdn.jsdelivr.net/gh/KRDS-uiux/krds-uiux@main/resources/fonts"
_PRETENDARD_CSS = ("https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9"
                   "/dist/web/static/pretendard.css")

# :root 변수는 토큰 dict 에서 생성한다(값을 두 군데 적지 않기 위해).
_VARS = "\n".join(f"  --k-{k}: {v};" for k, v in C.items())

# 아래 CSS 는 f-string 도 %-포매팅도 쓰지 않는다.
#  - f-string: CSS 의 { } 와 충돌
#  - %-포매팅: CSS 의 100% / 62.5% 같은 백분율과 충돌 (2026-08-16 실제로 터졌다)
# 그래서 __대문자__ 자리표시자를 .replace() 로 치환한다.
_CSS = """
@import url("__PRETENDARD__");

@font-face { font-family:"Pretendard GOV"; font-weight:400; font-style:normal; font-display:swap;
  src:url("__FONTCDN__/PretendardGOV-Regular.subset.woff2") format("woff2"); }
@font-face { font-family:"Pretendard GOV"; font-weight:500; font-style:normal; font-display:swap;
  src:url("__FONTCDN__/PretendardGOV-Medium.subset.woff2") format("woff2"); }
@font-face { font-family:"Pretendard GOV"; font-weight:700; font-style:normal; font-display:swap;
  src:url("__FONTCDN__/PretendardGOV-Bold.subset.woff2") format("woff2"); }

:root {
__VARS__
  --k-font: "Pretendard GOV","Pretendard",-apple-system,BlinkMacSystemFont,
            "Apple SD Gothic Neo","Malgun Gothic",sans-serif;
  --k-radius: 6px;
  --k-shadow-card: 0 1px 2px var(--k-shadow1), 0 4px 12px var(--k-shadow2);
}

/* ───────────── 기본 뼈대 ───────────── */
html, body, [class*="st-"], .stApp, button, input, textarea, select {
  font-family: var(--k-font) !important;
  -webkit-font-smoothing: antialiased;
  word-break: keep-all;            /* KRDS 한글 줄바꿈 규칙 */
}
.stApp { background: var(--k-gray5); }
[data-testid="stHeader"] { background: transparent; }

/* 본문 폭 — KRDS PC 컨테이너(1200px 급) + 대시보드용 여유 */
.stMainBlockContainer, [data-testid="stMainBlockContainer"] {
  max-width: 1440px; padding-top: 12px; padding-bottom: 72px;
}

/* 문단 · 목록 : KRDS body-medium(17px) / line-height 1.6 */
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li { font-size: 17px; line-height: 1.6; color: var(--k-gray90); }
[data-testid="stMarkdownContainer"] strong { font-weight: 700; color: var(--k-gray95); }
[data-testid="stMarkdownContainer"] code {
  font-size: 14px; background: var(--k-gray5); color: var(--k-primary70);
  border: 1px solid var(--k-gray10); border-radius: 4px; padding: 1px 5px;
}
a, a:visited { color: var(--k-primary60); }

/* ───────────── 상단 식별 바 (KRDS masthead 패턴 차용) ───────────── */
.k-masthead {
  background: var(--k-gray5); border-bottom: 1px solid var(--k-gray10);
  margin: -12px -1rem 0; padding: 7px 24px;
  font-size: 13px; color: var(--k-gray60); display: flex; gap: 8px; align-items: center;
}
.k-masthead .k-mast-dot {
  width: 6px; height: 6px; border-radius: 999px; background: var(--k-primary50); flex: none;
}
.k-masthead b { color: var(--k-gray80); font-weight: 700; }

/* ───────────── 페이지 헤더 ───────────── */
.k-pagehead {
  background: var(--k-gray0); border: 1px solid var(--k-gray10);
  border-radius: var(--k-radius); padding: 28px 32px; margin: 16px 0 28px;
  box-shadow: var(--k-shadow-card);
}
.k-pagehead .k-eyebrow {
  display: inline-block; font-size: 13px; font-weight: 700; letter-spacing: .02em;
  color: var(--k-primary60); background: var(--k-primary5);
  border: 1px solid var(--k-primary10); border-radius: 999px; padding: 3px 11px; margin-bottom: 12px;
}
.k-pagehead h1 { font-size: 32px; font-weight: 700; line-height: 1.35; color: var(--k-gray95); margin: 0; }
.k-pagehead .k-desc { font-size: 17px; color: var(--k-gray70); margin-top: 10px; line-height: 1.6; }
.k-metabar {
  display: flex; flex-wrap: wrap; gap: 0 28px; margin-top: 20px;
  padding-top: 16px; border-top: 1px solid var(--k-gray10);
}
.k-metabar .k-meta { display: flex; gap: 8px; align-items: baseline; font-size: 14px; }
.k-metabar .k-meta dt { color: var(--k-gray50); }
.k-metabar .k-meta dd { color: var(--k-gray90); font-weight: 700; margin: 0; }

/* ───────────── 섹션 제목 (KRDS heading + 좌측 강조선) ───────────── */
.k-section { margin: 32px 0 14px; }
.k-section h2 {
  font-size: 24px; font-weight: 700; color: var(--k-gray95); margin: 0;
  padding-left: 14px; border-left: 4px solid var(--k-primary50); line-height: 1.4;
}
.k-section h3 {
  font-size: 19px; font-weight: 700; color: var(--k-gray90); margin: 0;
  padding-left: 12px; border-left: 3px solid var(--k-gray30); line-height: 1.45;
}
.k-section .k-sub {
  font-size: 15px; color: var(--k-gray60); margin: 8px 0 0 18px; line-height: 1.6;
}

/* ───────────── 통계 카드 ───────────── */
.k-cards { display: grid; gap: 12px; margin: 4px 0 8px; }
.k-card {
  background: var(--k-gray0); border: 1px solid var(--k-gray10);
  border-radius: var(--k-radius); padding: 18px 20px; box-shadow: 0 1px 2px var(--k-shadow1);
  border-top: 3px solid var(--k-gray20);
}
.k-card .k-label {
  font-size: 14px; font-weight: 700; color: var(--k-gray60);
  display: flex; align-items: center; gap: 6px;
}
.k-card .k-value {
  font-size: 30px; font-weight: 700; color: var(--k-gray95);
  margin-top: 8px; line-height: 1.2; letter-spacing: -0.01em;
}
.k-card .k-value .k-unit { font-size: 16px; font-weight: 500; color: var(--k-gray60); margin-left: 3px; }
.k-card .k-sub { font-size: 13px; color: var(--k-gray50); margin-top: 7px; line-height: 1.5; }
.k-card.t-primary     { border-top-color: var(--k-primary50); }
.k-card.t-danger      { border-top-color: var(--k-danger50); }
.k-card.t-warning     { border-top-color: var(--k-warning50); }
.k-card.t-success     { border-top-color: var(--k-success50); }
.k-card.t-information { border-top-color: var(--k-information50); }
.k-card.t-point       { border-top-color: var(--k-point50); }
.k-card.t-secondary   { border-top-color: var(--k-secondary50); }

/* ───────────── 배지 / 태그 ───────────── */
.k-badge {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: 13px; font-weight: 700; line-height: 1;
  padding: 5px 10px; border-radius: 999px; border: 1px solid transparent; white-space: nowrap;
}
.k-badge.sq { border-radius: 4px; }

/* ───────────── 알림(KRDS critical alerts / info box) ───────────── */
.k-alert {
  border: 1px solid; border-left-width: 4px; border-radius: var(--k-radius);
  padding: 16px 20px; margin: 12px 0; font-size: 15px; line-height: 1.65;
}
.k-alert .k-alert-t { font-weight: 700; font-size: 16px; display: block; margin-bottom: 5px; }
.k-alert p { margin: 0; }
.k-alert code { background: rgba(0,0,0,.05); border-radius: 3px; padding: 1px 5px; font-size: 13px; }

/* ───────────── 도움말 캡션 ───────────── */
.k-note {
  font-size: 14px; color: var(--k-gray60); line-height: 1.6;
  background: var(--k-gray5); border-left: 3px solid var(--k-gray20);
  padding: 11px 14px; border-radius: 0 4px 4px 0; margin: 10px 0 14px;
}
.k-note code { background: var(--k-gray10); border-radius: 3px; padding: 1px 5px; font-size: 13px; }

/* ───────────── 구조화 목록(KRDS structured list) ───────────── */
.k-list { border-top: 2px solid var(--k-gray80); margin: 8px 0 4px; }
.k-list .k-row {
  display: flex; gap: 12px; align-items: baseline;
  padding: 11px 6px; border-bottom: 1px solid var(--k-gray10); font-size: 15px;
}
.k-list .k-row .k-rank {
  flex: none; width: 22px; height: 22px; border-radius: 999px; background: var(--k-gray5);
  color: var(--k-gray60); font-size: 12px; font-weight: 700;
  display: inline-flex; align-items: center; justify-content: center;
}
.k-list .k-row .k-name { flex: 1 1 auto; color: var(--k-gray90); font-weight: 500; min-width: 0;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.k-list .k-row .k-num { flex: none; font-weight: 700; color: var(--k-gray95); }
.k-list .k-row .k-meta { flex: none; font-size: 13px; color: var(--k-gray50); }

/* ───────────── 사이드 내비게이션(KRDS side navigation) ───────────── */
[data-testid="stSidebar"] { background: var(--k-gray0); border-right: 1px solid var(--k-gray10); }
[data-testid="stSidebar"] .stMainBlockContainer,
[data-testid="stSidebarUserContent"] { padding-top: 12px; }
.k-navbrand { padding: 6px 4px 14px; border-bottom: 2px solid var(--k-gray80); margin-bottom: 6px; }
.k-navbrand .k-nb-t { font-size: 17px; font-weight: 700; color: var(--k-gray95); line-height: 1.35; }
.k-navbrand .k-nb-s { font-size: 12px; color: var(--k-gray50); margin-top: 4px; }
.k-navgroup {
  font-size: 12px; font-weight: 700; color: var(--k-gray50); letter-spacing: .04em;
  padding: 16px 4px 4px;
}
/* st.button 을 KRDS 사이드 내비 항목처럼 (선택 상태 = type="primary") */
[data-testid="stSidebar"] .stButton { margin: 0; }
[data-testid="stSidebar"] .stButton > button {
  justify-content: flex-start; text-align: left;
  background: transparent; border: none; border-bottom: 1px solid var(--k-gray10);
  border-radius: 0 !important; box-shadow: none !important;
  padding: 11px 12px; font-size: 15px; font-weight: 500; color: var(--k-gray70);
  transition: background .12s, color .12s;
}
[data-testid="stSidebar"] .stButton > button:hover {
  background: var(--k-primary5); color: var(--k-primary60);
}
[data-testid="stSidebar"] .stButton > button[kind="primary"],
[data-testid="stSidebar"] .stButton > button[data-testid$="stBaseButton-primary"] {
  background: var(--k-primary5) !important; color: var(--k-primary60) !important;
  font-weight: 700 !important; box-shadow: inset 3px 0 0 var(--k-primary50) !important;
}
[data-testid="stSidebar"] .stButton > button p { font-size: 15px; }

/* st.radio 를 KRDS 사이드 내비처럼 (내비를 radio 로 바꿀 때를 대비한 예비 규칙) */
[data-testid="stSidebar"] [role="radiogroup"] { gap: 0 !important; }
[data-testid="stSidebar"] [role="radiogroup"] label {
  padding: 10px 12px !important; border-bottom: 1px solid var(--k-gray10);
  margin: 0 !important; width: 100%; transition: background .12s;
}
[data-testid="stSidebar"] [role="radiogroup"] label:hover { background: var(--k-primary5); }
[data-testid="stSidebar"] [role="radiogroup"] label p { font-size: 15px !important; color: var(--k-gray70); }
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
  background: var(--k-primary5); box-shadow: inset 3px 0 0 var(--k-primary50);
}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p {
  color: var(--k-primary60) !important; font-weight: 700 !important;
}

/* ───────────── 탭(보조로 남겨 둔 것) ───────────── */
.stTabs [data-baseweb="tab-list"] { gap: 2px; border-bottom: 1px solid var(--k-gray20); }
.stTabs [data-baseweb="tab"] { height: 46px; padding: 0 18px; font-size: 16px; font-weight: 700; }
.stTabs [data-baseweb="tab-highlight"] { background-color: var(--k-primary50); height: 3px; }
.stTabs [data-baseweb="tab-border"] { display: none; }

/* ───────────── 표 ───────────── */
[data-testid="stDataFrame"], [data-testid="stDataFrameResizable"] {
  border-radius: var(--k-radius); overflow: hidden;
}
[data-testid="stDataFrame"] * { font-size: 14px; }

/* ───────────── 아코디언(KRDS accordion) ───────────── */
[data-testid="stExpander"] {
  border: 1px solid var(--k-gray20) !important; border-radius: var(--k-radius) !important;
  background: var(--k-gray0); margin-bottom: 8px; box-shadow: none !important;
}
[data-testid="stExpander"] summary { padding: 13px 16px !important; }
[data-testid="stExpander"] summary:hover { background: var(--k-primary5); }
[data-testid="stExpander"] summary p { font-size: 15px !important; font-weight: 700 !important;
  color: var(--k-gray90) !important; }

/* ───────────── 입력 위젯 ───────────── */
[data-testid="stWidgetLabel"] p { font-size: 14px !important; font-weight: 700 !important;
  color: var(--k-gray70) !important; }
[data-baseweb="tag"] {
  background-color: var(--k-primary5) !important; color: var(--k-primary60) !important;
  border: 1px solid var(--k-primary20) !important; border-radius: 4px !important;
}
[data-baseweb="tag"] span { color: var(--k-primary60) !important; }

/* ───────────── 네이티브 알림(st.info/success/...) 도 KRDS 톤으로 ───────────── */
[data-testid="stAlert"] { border-radius: var(--k-radius); border-left-width: 4px; font-size: 15px; }

/* ───────────── 푸터 ───────────── */
.k-footer {
  margin-top: 44px; padding: 22px 24px; background: var(--k-gray90);
  border-radius: var(--k-radius); color: var(--k-gray30); font-size: 13px; line-height: 1.7;
}
.k-footer b { color: var(--k-gray0); font-weight: 700; }
.k-footer .k-fsep { color: var(--k-gray60); margin: 0 8px; }
"""
_CSS = (_CSS.replace("__PRETENDARD__", _PRETENDARD_CSS)
            .replace("__FONTCDN__", _FONT_CDN)
            .replace("__VARS__", _VARS))


def setup() -> None:
    """CSS 주입. `st.set_page_config()` 직후 딱 한 번 부른다."""
    st.markdown(f"<style>{_CSS}</style>", unsafe_allow_html=True)


def _md(html_str: str) -> None:
    st.markdown(html_str, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════ 3. 컴포넌트
def masthead(left: str, right: str = "") -> None:
    """상단 식별 바. KRDS masthead 의 *형태만* 차용한 내부 시스템 표기."""
    r = f'<span style="margin-left:auto">{e(right)}</span>' if right else ""
    _md(f'<div class="k-masthead"><span class="k-mast-dot"></span>{left}{r}</div>')


def page_header(title: str, desc: str = "", meta: Sequence[tuple[str, str]] = (),
                eyebrow: str = "") -> None:
    """페이지 제목 영역. meta 는 (라벨, 값) 쌍."""
    parts = ['<div class="k-pagehead">']
    if eyebrow:
        parts.append(f'<span class="k-eyebrow">{e(eyebrow)}</span>')
    parts.append(f"<h1>{e(title)}</h1>")
    if desc:
        parts.append(f'<div class="k-desc">{desc}</div>')
    if meta:
        rows = "".join(
            f'<dl class="k-meta"><dt>{e(k)}</dt><dd>{e(v)}</dd></dl>' for k, v in meta)
        parts.append(f'<div class="k-metabar">{rows}</div>')
    parts.append("</div>")
    _md("".join(parts))


def section(title: str, sub: str = "", level: int = 2) -> None:
    """섹션 제목. level 2 = 주요 섹션(파란 강조선), 3 = 하위 섹션(회색)."""
    tag = "h2" if level == 2 else "h3"
    s = f'<div class="k-sub">{sub}</div>' if sub else ""
    _md(f'<div class="k-section"><{tag}>{e(title)}</{tag}>{s}</div>')


def cards(items: Iterable[dict], cols: int = 4) -> None:
    """통계 카드 그리드.

    items 원소: {"label": str, "value": str, "sub": str(옵션),
                 "unit": str(옵션), "tone": str(옵션)}
    """
    body = []
    for it in items:
        t = it.get("tone", "default")
        unit = f'<span class="k-unit">{e(it["unit"])}</span>' if it.get("unit") else ""
        sub = f'<div class="k-sub">{it["sub"]}</div>' if it.get("sub") else ""
        body.append(
            f'<div class="k-card t-{e(t)}">'
            f'<div class="k-label">{e(it["label"])}</div>'
            f'<div class="k-value">{e(it["value"])}{unit}</div>{sub}</div>')
    _md(f'<div class="k-cards" style="grid-template-columns:repeat({cols},minmax(0,1fr))">'
        + "".join(body) + "</div>")


def badge(text: str, kind: str = "gray", square: bool = False) -> str:
    """배지 HTML 문자열을 **반환**한다(다른 HTML 안에 끼워 쓰기 위해)."""
    bg, bd, fg = tone(kind)
    sq = " sq" if square else ""
    return (f'<span class="k-badge{sq}" style="background:{bg};border-color:{bd};color:{fg}">'
            f"{e(text)}</span>")


def alert(kind: str, title: str, body: str = "") -> None:
    """KRDS 알림 박스. kind: danger / warning / success / information / primary / gray."""
    bg, bd, fg = tone(kind)
    b = f"<p>{body}</p>" if body else ""
    _md(f'<div class="k-alert" style="background:{bg};border-color:{bd};color:{fg}">'
        f'<span class="k-alert-t">{title}</span>{b}</div>')


def note(text: str) -> None:
    """표·차트 밑에 붙이는 해설. **HTML 을 그대로 넣는다**(코드 강조용 <code> 허용)."""
    _md(f'<div class="k-note">{text}</div>')


def rows(items: Iterable[tuple[str, str, str]], ranked: bool = True) -> None:
    """구조화 목록. 원소 = (이름, 강조값, 부가설명)."""
    out = []
    for i, (name, num, meta) in enumerate(items, 1):
        rk = f'<span class="k-rank">{i}</span>' if ranked else ""
        m = f'<span class="k-meta">{e(meta)}</span>' if meta else ""
        out.append(f'<div class="k-row">{rk}<span class="k-name">{e(name)}</span>'
                   f'<span class="k-num">{e(num)}</span>{m}</div>')
    _md(f'<div class="k-list">{"".join(out)}</div>')


def nav_brand(title: str, sub: str = "") -> None:
    s = f'<div class="k-nb-s">{e(sub)}</div>' if sub else ""
    _md(f'<div class="k-navbrand"><div class="k-nb-t">{e(title)}</div>{s}</div>')


def nav_group(label: str) -> None:
    _md(f'<div class="k-navgroup">{e(label)}</div>')


def footer(lines: Sequence[str]) -> None:
    _md('<div class="k-footer">' + "<br>".join(lines) + "</div>")


# ══════════════════════════════════════════════════════════ 4. 도메인 매핑
# 등급·리스크를 KRDS 시스템 컬러에 대응시킨다. 앱 전체가 같은 색을 쓰게 하기 위해 여기 둔다.
GRADE_TONE = {"S": "primary", "A": "success", "B": "gray",
              "C": "warning", "D": "danger"}
RISK_TONE = {"높음": "danger", "중간": "warning", "낮음": "success", "없음": "gray"}
SEVERITY_TONE = {3: "danger", 2: "warning", 1: "information"}


def grade_badge(g: str) -> str:
    return badge(str(g), GRADE_TONE.get(str(g), "gray"), square=True)


def risk_badge(r: str) -> str:
    return badge(str(r), RISK_TONE.get(str(r), "gray"), square=True)
