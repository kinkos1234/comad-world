### T0. 온보딩 (첫 세션 감지)

**감지 조건:** 프로젝트에 `.comad/` 폴더가 없거나, 첫 대화 시작 시

**실행 절차:**

1. **프로젝트 탐색** — 탐색자(haiku) 에이전트로 자동 수행

   수집 항목:
   - 주 언어 / 프레임워크 감지 (package.json, pyproject.toml, go.mod, Cargo.toml 등)
   - 디렉토리 구조 파악 (src/, lib/, tests/, docs/ 등)
   - 테스트 프레임워크 감지 (jest, pytest, go test 등)
   - 빌드 도구 감지 (webpack, vite, make, cargo 등)
   - 프로덕션 환경 감지 (Dockerfile, fly.toml, vercel.json, k8s/ 등)
   - git 상태 확인 (init 여부, 리모트 설정, 최근 커밋)

2. **`.comad/` 폴더 생성**

   ```
   .comad/
     research/          # 조사 단계 산출물
     plans/             # 분해 결과, 실행 계획
     experiments/       # 실험 로그
     sessions/          # 세션 저장 (T5)
     state.json         # 현재 진행 상태
   ```

   `state.json` 초기 내용:
   ```json
   {
     "project": "프로젝트명",
     "language": "감지된 주 언어",
     "framework": "감지된 프레임워크",
     "created": "ISO 날짜",
     "sessions": 0,
     "experiments": 0,
     "production": false
   }
   ```

3. **환영 메시지 출력**

   ```
   Comad Voice가 이 프로젝트를 파악했습니다.

   프로젝트: [프로젝트명]
   주 언어: [감지된 언어]
   프레임워크: [감지된 프레임워크]
   구조: [주요 디렉토리 요약]

   준비 완료! 다음 중 하나를 시도해보세요:
   - "검토해봐" → 현재 상태 진단 + 개선 카드
   - "알아서 다 해줘" → 전체 자동 파이프라인
   - "레포 꾸며줘" → GitHub 레포 광택
   ```

4. **프로덕션 환경 감지 시 추가 안내**

   Dockerfile, fly.toml 등이 발견되면:
   ```
   프로덕션 환경이 감지되었습니다.
   파일 수정 시 안전 프로토콜이 자동 적용됩니다.
   (위험한 명령 실행 전 확인을 받습니다)
   ```

5. **이후 세션**: `.comad/` 존재 확인 → 온보딩 스킵, `state.json`의 sessions 카운트 증가
