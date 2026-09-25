# Intent — shadow_wik sensory trading system

## Outcome
실시간 시장 상태를 정보 나열이 아니라 검증 가능한 감각 신호로 변환해, 사람이 거래 참여 시점과 위험 변화를 빠르게 알아차리게 한다. 모든 거래는 매수에서 시작해 매도로 종료되는 하나의 생명주기로 취급하며, 진입 시점에 30분/당일/3일/1주/1개월/3개월/6개월/실적발표·예정뉴스 같은 이벤트 기반 종료범위를 미리 고정한다. 매도 국면에서는 남은 시간, 이벤트, 현재 손익, 시장 구조, 수급, 뉴스, Persona, Jev 불확실성을 하나의 최종 선택으로 집중시키고, 매도 후 결과와 성공/실패 판정을 거래 이력에 남겨 다음 Evidence로 사용한다. 가상매매 단계에서는 공개 연구와 반복 거래 노하우를 `scalp pattern hypothesis`로 구조화하고, Jev가 현재 시장 상태가 각 패턴에 부합할 확률을 별도 질문으로 평가한다. Dashboard는 통계 검증 강도를 0~100으로 조절하며 0은 검증 전 탐색, 100은 가장 엄격한 내부 paper evidence 요구를 뜻한다. 기본값은 0으로 두어 paper 표본을 빠르게 축적한다. 가상 포트폴리오 기준 시드머니는 100,000,000 KRW이며 레버리지를 사용하지 않고 기본 패턴당 10%를 배정해 최대 10개 동시 포지션까지만 허용한다. 기술적 회귀 통과만으로는 개발종료를 선언하지 않는다. 비용을 반영한 실제 체결 표본에서 반복 가능한 수익성이 검증되어야 수동운영 종료 경로가 열리고, 자동주문 운영을 최종형으로 선택할 경우에는 그 수익성 검증에 더해 사전 위험제한·중복주문 방지·stale-data 차단·kill switch·사후 체결대사와 별도의 명시적 인간 승인이 모두 통과해야 종료 경로가 열린다.

## Primary operating mode — opening 60 minutes
- 주력 운용창은 KRX 장 시작 직후 60분(09:00~09:59) 하나로 제한한다.
- 매일 현재 상태를 `buy_state` 또는 `sell_state` 중 하나로 본다. `sell_state`는 현금/관망을 포함한다.
- `buy_state`에서는 같은 60분 안에서 `hold/reduce/exit`를 판단하며 손실 회피를 이유로 장기 thesis로 연장하지 않는다.
- `sell_state`에서는 `enter/wait/observe_today`를 판단한다. 진입 근거가 없으면 하루 종일 관망할 수 있다.
- 놓친 상승은 실현손실이 아니다. 아직 가지지 않은 수익을 회복해야 할 돈처럼 취급하지 않는다.
- 가격이 하락했다는 이유만으로 기회로 간주하지 않는다. 하락 흐름의 중단·안정·반전 Evidence가 따로 필요하다.
- Jev는 오프닝 60분의 완료된 1분 봉마다 현재 당일 흐름, FOMO 위험, 하락 기회착시 위험, 객관성 이탈 위험을 재평가한다.
- 실시간 감각축은 Trend continuation / Breakout / Pullback / Volatility contraction→expansion / Mean reversion / Information-event drift / Supply-demand-liquidity imbalance의 7개 원시 메커니즘으로 압축한다. 각 값은 현재 메커니즘 활성 확률이며 수익확률로 해석하지 않는다.
- 매매기법의 이름·유파 수를 늘리는 대신 위 7개 축의 조합으로 해석하며, 이름 자체를 신규 판단축으로 자동 증식하지 않는다.
- 장기투자 포지션은 소액·저관여 별도 영역으로 취급하며 오프닝 60분 단기 thesis의 근거 또는 구조용 핑계로 사용하지 않는다.

## Beneficiary and operating conditions
- 사용자는 실제 거래 결정을 직접 내리는 사람이다.
- 시스템은 intraday 관측, 시장 미세구조, 뉴스/수급, Persona/Regime, Jev 확률을 사용한다.
- 시장 데이터와 브라우저/증권 API 관측은 timestamp/freshness가 명확해야 한다.
- 가상 체결은 패턴 성립 시점의 실제 관측 가격을 기준으로 하며 수수료와 슬리피지를 포함한다.
- 실제 거래 기록은 진입 시 종료범위를 반드시 갖고, 이벤트 기반이면 이벤트 이름과 예정시각을 함께 기록한다.
- 종료 검증에 사용하는 실전 거래는 `live_real`로 명시적으로 분류된 실제 체결만 인정하며 paper/synthetic/unverified 거래는 실전 수익성 Evidence에 포함하지 않는다.
- 실전 수익성 정책의 최초 기준은 프로젝트 내부 검증 기준이며 보편적 투자 성공 기준으로 주장하지 않는다.

## Excellence criteria
1. 측정값, 추론값, Jev 확률, Unknown을 시각적으로 구분한다.
2. 같은 상태를 반복 관찰할 때 방향·속도·압력·불확실성의 의미가 일관된다.
3. 사람이 보는 핵심 패턴 축은 높을수록 좋은 방향으로 정규화한다.
4. 한 번의 최근 경험으로 가중치나 시각문법을 자동 변경하지 않는다.
5. 반복된 거래 경험은 측정/모델/시각표현/인간해석 오류로 분리되어 수정 후보를 만든다.
6. Jev raw probability와 실현 빈도 calibration을 구분한다.
7. 패턴 성립 시점에 가상 진입을 기록하고 TP/SL/시간/패턴붕괴 규칙으로 가상 청산한다.
8. 패턴별 순수익률, 승률, 평균수익률, 복리수익률, profit factor, MFE/MAE를 실제 체결 비용 포함 기준으로 축적한다.
9. 거래 진입 시 `30m/day/3d/1w/1m/3m/6m/event` 중 종료범위를 기록하고, Jev는 그 범위를 임의로 늘리지 않는다.
10. 매도 판단 시 Jev는 원래 thesis 유지 여부, 남은 horizon의 보유가치, 매도 원인, 매도 긴급도를 계산한 뒤 `hold/reduce/exit` 하나로 집중한다.
11. 거래 이력은 진입가·진입시각·종료범위·이벤트·매도시각·매도가·최종 Jev 판단·순수익률·성공/실패·판정근거를 함께 보존한다.
12. 실제 주문 실행은 사람에게 남겨 두고 자동화 권한은 별도 실증과 명시적 승인 전에는 확대하지 않는다.
13. 실전 수익성 Gate는 `live_real` 실제 체결만 사용하고, 비용 반영 순수익률에 대해 최소 표본·거래일수·양의 평균수익·통계적 양의 우위·Profit Factor·낙폭·수익 집중도를 동시에 검증한다.
14. 표본 부족은 PASS가 아니라 OPEN으로 남기며 paper/synthetic 성과가 실전 Gate를 통과시키지 못한다.
15. 자동주문 권한 Gate는 실전 수익성 PASS를 선행조건으로 하고, 사전 주문한도·오류/중복주문 차단·stale-data 거부·symbol allowlist·주문속도 제한·kill switch·사후 체결대사·실거래/모의 분리를 검증한다.
16. 자동주문 권한은 설정파일만으로 승인되지 않으며 `D9_AUTOMATION_AUTHORITY`에 대한 실제 사용자의 명시적 승인 Evidence가 있어야 한다.
17. 최종 개발종료는 기술 회귀 M7과 실전 수익성 M8이 PASS한 수동운영 경로, 또는 M8에 더해 자동주문 권한 M9까지 PASS한 자동운영 경로 중 하나가 성립한 뒤 인간의 최종 종료 선언으로 확정한다.
18. 단타 노하우 패턴은 연구/경험 근거와 반증조건을 가진 hypothesis로만 시작하며 Jev pattern probability와 paper outcome을 분리해 기록한다.
19. Dashboard 통계 검증 강도 0은 통계적 유의성을 뜻하지 않고 탐색 허용을 뜻한다. 높은 slider 값만 paper history의 양의 평균·표본수·p-value 기반 evidence-strength gate를 요구한다.
20. 1억 원 가상 포트폴리오는 paper-only이며 기본 패턴당 10%, 최대 10개 동시 포지션, 무레버리지로 운용하고 모든 실현 손익은 비용 반영 paper return에서 계산한다.

## Constraints
- 새로운 오케스트레이션 서비스, 에이전트 조직, 큐, 벡터DB를 만들지 않는다.
- 기존 `MarketSnapshot → features → persona → Jev → signal` 구조를 재사용한다.
- 외부 API 키, 주문권한, 배포, 결제는 자동으로 수행하지 않는다.
- 최근 경험과 최신 뉴스가 확신을 만들었을 가능성을 항상 별도 위험으로 본다.
- 최초 패턴 임계값은 SYNTHETIC 가설로 취급하며 수익성이 검증된 규칙으로 표현하지 않는다.
- `hold/reduce/exit`는 advisory이며 실제 매도는 사람의 행동으로만 종료 처리한다.
- 짧게 시작한 거래를 손실 회피를 이유로 더 긴 horizon으로 자동 변환하지 않는다.
- `live_real` 여부를 추정하거나 paper/synthetic 기록을 실거래로 승격하지 않는다.
- Dashboard slider를 낮추는 행위는 실전 수익성 Gate M8을 낮추지 않으며 exploratory paper 거래만 늘린다.
- 단타 pattern probability는 Jev raw model output이며 실제 승률이나 통계적 유의확률로 표시하지 않는다.
- 자동주문 승인 Evidence가 없으면 실주문 기능을 활성화하거나 권한이 있다고 가정하지 않는다.
- 자동주문 안전 Gate는 법률·규제 적합성의 대체물이 아니며 실제 사용하는 브로커/시장 규칙은 별도로 확인한다.

## Autonomous scope
AI는 로컬/저장소 내 가역적 코드·테스트·문서 수정, replay 분석, 가상체결, 성과집계, 거래 이력 기록, Jev 매도분석, 실전 수익성 Gate 계산, 자동주문 안전성 Gate 검사, 수정 후보 생성까지 수행할 수 있다.

## Human-reserved decisions
- 실제 주문/포지션 변경
- 실제 매도 실행과 부분매도 비율
- 실거래 자동화 권한 확대
- 시각표현이 실제 감각과 맞는지에 대한 최종 평가
- 단일 실패를 예외적으로 즉시 규칙에 반영하는 결정
- 패턴 임계값을 실거래 자동화 기준으로 승격하는 결정
- 성공/실패 자동판정을 수동으로 뒤집는 최종 평가
- 실제 체결을 `live_real`로 확정하는 행위(브로커 체결 원장으로 직접 확인되지 않는 경우)
- `D9_AUTOMATION_AUTHORITY` 자동주문 권한 승인
- `D10_DECLARE_COMPLETE` 최종 개발종료 선언

## Failure owner
측정·모델·시각화·해석·체결가정·horizon 설정 중 어느 층이 실패했는지 Harness가 분리하고, 분리되지 않으면 `unknown`으로 남긴다. 원인을 억지로 만들지 않는다.

## Budget and stop rules
- 외부 유료 호출과 자동매매 권한 확대 없음. 이번 Intent 변경은 자동주문 권한 승인이 아니다.
- 같은 수정 가설이 두 번 연속 개선을 만들지 못하면 추가 수정 대신 재검토한다.
- 구조적 원인이 불명확하면 새 아키텍처를 만들지 않고 현재 노드에서 멈춘다.
- 가상수익은 실제 주문 성과로 간주하지 않는다.
- 종료범위가 만료되면 신규 장기 thesis를 자동 생성하지 않고 매도 재평가를 최우선으로 한다.

## Completion criteria
- Intent와 Execution Graph가 구조 검증을 통과한다.
- 시각문법, 경험 Harness, fingerprint, pattern-triggered paper trading, trade lifecycle/history 단위 테스트가 통과한다.
- 실시간 stream에 open trade를 연결하면 남은 horizon과 Jev sell-focus가 매 프레임 출력된다.
- 매도 기록 후 수익률과 성공/실패 판정이 거래 이력에 보존된다.
- M1~M7 기술 Gate가 통과해도 개발종료를 선언하지 않는다.
- M8 실전 수익성 Gate가 PASS하면 수동운영 기준의 종료 선언 자격이 생긴다.
- 자동주문 운영을 종료형으로 선택하면 M8 PASS 이후 M9 자동주문 권한 Gate까지 PASS해야 종료 선언 자격이 생긴다.
- 마지막 `D10_DECLARE_COMPLETE`는 실제 사용자의 명시적 결정으로만 확정한다.
- 실전 수익성 또는 자동주문 권한 Evidence가 부족하면 상태를 OPEN/ESCALATE로 남기며 기술 테스트 결과로 대체하지 않는다.
