# Intent — shadow_wik sensory trading system

## Outcome
실시간 시장 상태를 정보 나열이 아니라 검증 가능한 감각 신호로 변환해, 사람이 거래 참여 시점과 위험 변화를 빠르게 알아차리게 한다. 거래 경험은 다음 판단의 Evidence가 되며, AI는 반복된 오류만 시각표현·모델·측정 규칙의 수정 후보로 올린다.

## Beneficiary and operating conditions
- 사용자는 실제 거래 결정을 직접 내리는 사람이다.
- 시스템은 intraday 관측, 시장 미세구조, 뉴스/수급, Persona/Regime, Jev 확률을 사용한다.
- 시장 데이터와 브라우저 관측은 timestamp/freshness가 명확해야 한다.

## Excellence criteria
1. 측정값, 추론값, Jev 확률, Unknown을 시각적으로 구분한다.
2. 같은 상태를 반복 관찰할 때 방향·속도·압력·불확실성의 의미가 일관된다.
3. 한 번의 최근 경험으로 가중치나 시각문법을 자동 변경하지 않는다.
4. 반복된 거래 경험은 측정/모델/시각표현/인간해석 오류로 분리되어 수정 후보를 만든다.
5. Jev raw probability와 실현 빈도 calibration을 구분한다.
6. 주문 실행은 사람에게 남겨 두고 시스템은 신호와 근거까지만 제공한다.

## Constraints
- 새로운 오케스트레이션 서비스, 에이전트 조직, 큐, 벡터DB를 만들지 않는다.
- 기존 `MarketSnapshot → features → persona → Jev → signal` 구조를 재사용한다.
- 외부 API 키, 주문권한, 배포, 결제는 자동으로 수행하지 않는다.
- 최근 경험과 최신 뉴스가 확신을 만들었을 가능성을 항상 별도 위험으로 본다.

## Autonomous scope
AI는 로컬/저장소 내 가역적 코드·테스트·문서 수정, replay 분석, 수정 후보 생성까지 수행할 수 있다.

## Human-reserved decisions
- 실제 주문/포지션 변경
- 실거래 자동화 권한 확대
- 시각표현이 실제 감각과 맞는지에 대한 최종 평가
- 단일 실패를 예외적으로 즉시 규칙에 반영하는 결정

## Failure owner
측정·모델·시각화·해석 중 어느 층이 실패했는지 Harness가 분리하고, 분리되지 않으면 `unknown`으로 남긴다. 원인을 억지로 만들지 않는다.

## Budget and stop rules
- 외부 유료 호출과 자동매매 권한 확대 없음.
- 같은 수정 가설이 두 번 연속 개선을 만들지 못하면 추가 수정 대신 재검토한다.
- 구조적 원인이 불명확하면 새 아키텍처를 만들지 않고 현재 노드에서 멈춘다.

## Completion criteria
- Intent와 Execution Graph가 구조 검증을 통과한다.
- 시각문법과 경험 Harness 단위 테스트가 통과한다.
- 실제 거래 데이터 검증 전에는 기술적 완료만 주장하고, 실전 성과 gate는 열린 상태로 남긴다.
