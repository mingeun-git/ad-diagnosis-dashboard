# 광고 선별(진단) 시스템 — 대시보드

리워드 광고 플랫폼의 광고 9,389건을 **제목·설명문만으로 진단**하는 운영진용 대시보드.
LLM 태그 15축 + 텍스트 피처(TF-IDF/SVD)로 성과 이력이 없는 신규 광고에도 기대 CVR 과 등급을 매긴다.
데이터는 BigQuery 에서 실시간으로 읽는다(접속 정보는 Secrets 로 주입).

## 화면 구성 (좌측 내비게이션)
| 그룹 | 메뉴 | 내용 |
|---|---|---|
| 진단 요약 | 재고 진단 | 광고 구성 · 기존 분류축과 비교 |
| 태그 성과 분석 | 성과 스코어보드 | 태그별 CVR 순위 |
| | 마찰 분석 ★ | 어떤 참여 조건이 전환을 깎는가 |
| | 유통 갭 | 매체별 미노출 우수 광고 추천 |
| 광고 단위 조회 | 광고 카드 | 광고별 기대 CVR · 등급 검색 |
| | 리스크 경보 | 위험 · 고마찰 광고 |
| | 신규 광고 | 성과 이력 없는 신규 광고 진단 (시연용 합성 데이터 포함) |
| 시스템 신뢰도 | 검증 결과 | 게이트 검증 · 피처 구성 비교 · 모델 비교 |

## 디자인 — KRDS 적용
화면은 **KRDS(대한민국 정부 디자인 시스템) v1.0.0** 의 규칙을 따른다.

| 파일 | 역할 |
|---|---|
| `.streamlit/config.toml` | 색 · 서체 · 모서리 등 Streamlit 네이티브 테마 (KRDS 토큰 매핑) |
| `krds.py` | 레이아웃 · 컴포넌트 · CSS. **생김새를 고칠 일은 전부 이 파일 하나** |
| `krds_tokens_reference.css` | KRDS 공식 토큰 원본 사본 (출처 확인용, 앱은 읽지 않음) |
| `app.py` | 데이터 로직만. **CSS 를 쓰지 않는다** |

- 토큰 출처: <https://github.com/KRDS-uiux/krds-uiux> → `resources/css/token/krds_tokens.css`
- 서체: Pretendard GOV (jsDelivr CDN). 서브셋에 없는 글자는 Pretendard 로 폴백.
- ⚠️ **정부상징 · masthead(정부 누리집 식별 배너)는 쓰지 않았다.** 이 서비스는 정부 서비스가
  아니므로 그대로 쓰면 사칭이 된다. 컬러 · 타이포 · 간격 · 컴포넌트 형태만 차용했다.

## 로컬 실행
```bash
pip install -r requirements.txt
streamlit run app.py
```
로컬에서는 `gcloud auth application-default login` 이 되어 있으면 그대로 붙는다.
`.streamlit/secrets.toml` 이 아예 없으면 로컬 파케이 모드로 떨어지고, 그 파일도 없으면
"산출물이 없습니다" 안내가 뜬다(크래시하지 않는다).

## 배포 (Streamlit Community Cloud)
1. 이 폴더를 GitHub 저장소로 push
2. <https://share.streamlit.io> → New app → 저장소 선택 → `app.py`
3. Advanced settings → Secrets 에 `.streamlit/secrets.toml.example` 내용을 실제 값으로 채워 붙여넣기

> `requirements.txt` 의 `streamlit>=1.50` 핀을 낮추지 말 것.
> `config.toml` 의 `fontFaces` · `baseRadius` · `chartCategoricalColors` 는 1.46+ 에서만 동작한다.

## 데이터에 대한 주의
- **`ads_idx >= 990000` 은 시연용 합성 데이터**다. 실제 운영 로그가 아니므로 수치를 인용하지 말 것.
- 신규 광고의 기대 CVR 은 **절대값이 아니라 순위**로 볼 것 (‘신규 광고’ 화면 하단 설명 참조).
- CVR 42.6% 는 **어뷰징 전처리 후** 값이다(원본 8.75%). 외부 인용 시 반드시 병기.
- 이 저장소에는 개인정보가 포함된 컬럼(`user_ip` 등)이 어떤 형태로도 들어 있지 않다.
