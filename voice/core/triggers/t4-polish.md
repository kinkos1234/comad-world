### T4. 레포 광택 (Repo Polish)

**감지 키워드:** "광택", "레포 정리", "repo polish", "배포 준비", "GitHub 정리", "레포 꾸며줘", "professional하게", "허접해 보여"

GitHub 레포를 인기 오픈소스 수준으로 자동 포장하는 트리거.
코드 품질이 아니라 레포의 **포장(presentation)** 을 개선한다.

참고한 인기 도구들:
- github-readme-stats (78.9k stars) — 라이브 스탯 카드
- Best-README-Template (15.9k) — 섹션 구조 표준
- socialify (2.2k) — Social preview as a service
- git-cliff (11.6k) — 커밋 기반 CHANGELOG 자동 생성
- all-contributors — 기여자 테이블 자동 생성

**실행 절차:**

1. **SCAN** — 레포 구조 + 메타데이터 자동 수집

   파일 존재 여부 체크:
   - README.md (뱃지, TOC, 히어로, 섹션 구조)
   - .gitignore, LICENSE, CHANGELOG.md
   - CONTRIBUTING.md, CODE_OF_CONDUCT.md, SECURITY.md
   - .github/ISSUE_TEMPLATE/, .github/PULL_REQUEST_TEMPLATE.md
   - .github/workflows/ (CI/CD)
   - Social preview 이미지
   - Git tag / GitHub Release

   메타데이터 자동 수집 (readme-md-generator 패턴):
   - `git remote get-url origin` → GitHub owner/repo 추출
   - `package.json` / `pyproject.toml` / `go.mod` / `Cargo.toml` → 프로젝트명, 버전, 설명, 라이선스
   - `git log --format=%s` → 최근 커밋 메시지에서 프로젝트 성격 파악
   - 주 언어 감지 → .gitignore 템플릿 선택
   - 기존 README 구조 분석 → 어떤 섹션이 이미 있는지 파악

2. **DIAGNOSE** — README 점수 매기기 + 갭 카드 제시

   README 스코어링 (awesome-readme 기준, 10점 만점):

   | 항목 | 배점 | 기준 |
   |------|------|------|
   | 히어로 섹션 | 1점 | 센터 정렬 로고/이미지 + 한 줄 설명 |
   | 뱃지 | 1점 | License, Version, CI status 등 2개 이상 |
   | 목차 (TOC) | 1점 | 섹션 5개 이상이면 필수 |
   | 스크린샷/데모 | 1점 | GIF, 이미지, 또는 라이브 데모 링크 |
   | 설치 방법 | 1점 | 코드 블록으로 복붙 가능한 설치 명령 |
   | 사용법/예제 | 1점 | 최소 1개 코드 예제 |
   | 기여 가이드 링크 | 0.5점 | CONTRIBUTING.md 링크 |
   | 라이선스 명시 | 0.5점 | LICENSE 파일 + README에 표시 |
   | 크레딧/감사 | 0.5점 | 의존 도구, 영감 출처 |
   | Built With 뱃지 | 0.5점 | 사용 기술 스택 뱃지 그리드 |
   | 프로젝트 구조 | 0.5점 | 디렉토리 트리 또는 아키텍처 설명 |
   | Repo 인프라 | 0.5점 | Issue 템플릿, PR 템플릿, CI, Social preview |

   점수와 함께 갭 카드를 제시:

   ```
   ## 레포 광택 진단 — 현재 점수: 3.5/10

   ### 카드 1: README 구조 재설계 — 난이도 낮 / 효과 높
   - 현재: 뱃지 없음, TOC 없음, 히어로 없음 → 3점 누락
   - 개선: Best-README-Template 기반 섹션 구조 적용
     - 센터 정렬 히어로 (프로젝트명 + 한 줄 설명 + 로고)
     - shields.io 뱃지 행 (License, Version, CI, Made with)
     - TOC (자동 생성)
     - Built With 뱃지 그리드 (사용 기술 스택)
     - 프로젝트 구조 트리
   - 이걸 하면: README 점수 3.5 → 7.5 (+4점), 첫인상이 프로 레포

   ### 카드 2: 라이브 스탯 & 위젯 — 난이도 낮 / 효과 중
   - 현재: 정적 README, 동적 정보 없음
   - 개선:
     - github-readme-stats 카드 (스타, 포크, 이슈 수 실시간 표시)
     - 기여자 테이블 (all-contributors 패턴)
     - Star History 차트 (star-history.com 임베드)
   - 이걸 하면: README가 살아있는 느낌, 프로젝트 활성도 어필

   ### 카드 3: 커뮤니티 인프라 — 난이도 낮 / 효과 중
   - 현재: CONTRIBUTING, CODE_OF_CONDUCT, SECURITY 없음
   - 개선: 프로젝트 언어에 맞는 템플릿 자동 생성
   - 이걸 하면: GitHub Community Standards 점수 100%

   ### 카드 4: Issue/PR 템플릿 — 난이도 낮 / 효과 중
   - 현재: .github/ 폴더 없음
   - 개선: YAML forms 기반 Bug Report, Feature Request, PR 체크리스트
   - 이걸 하면: 기여자가 구조화된 양식으로 소통

   ### 카드 5: 릴리스 파이프라인 — 난이도 중 / 효과 높
   - 현재: Git tag 없음, CHANGELOG 없음
   - 개선:
     - CHANGELOG.md (Keep a Changelog 형식)
     - Git tag v{version} + GitHub Release
     - (선택) git-cliff 설정으로 커밋 → CHANGELOG 자동 변환
   - 이걸 하면: 버전 관리가 프로페셔널, 릴리스 노트 자동화

   ### 카드 6: Social Preview — 난이도 중 / 효과 높
   - 현재: 공유 시 썸네일 없음
   - 개선 (2가지 방식):
     - 즉시: socialify.git.ci URL로 자동 생성 (제로 메인터넌스)
     - 커스텀: Pencil MCP로 브랜드 이미지 1280x640 직접 제작
   - 이걸 하면: SNS/슬랙 공유 시 눈에 띄는 썸네일

   ### 카드 7: CI/CD 품질 게이트 — 난이도 중 / 효과 중
   - 현재: 워크플로우 없음
   - 개선: markdown lint + 필수 파일 체크 + `.markdownlint-cli2.jsonc` 자동 생성
   - 이걸 하면: PR마다 자동 품질 검증, 한국어 문서/CHANGELOG 린트 충돌 사전 방지

   현재 README 점수: 3.5/10
   전부 적용 시 예상 점수: 9.5/10
   어떤 카드를 진행할까요? (번호 선택 또는 "전부 다")
   ```

3. **GENERATE** — 선택된 카드의 파일들을 프로젝트에 맞게 자동 생성

   README 생성 규칙 (Best-README-Template + awesome-readme 기반):

   **필수 섹션 (순서대로):**
   ```markdown
   <!-- 히어로: 센터 정렬 -->
   <p align="center">로고 또는 스크린샷</p>
   <h1 align="center">프로젝트명</h1>
   <p align="center">한 줄 설명</p>
   <p align="center">뱃지 행</p>

   ## 목차 (TOC)
   ## 소개 / About
   ## 스크린샷 / 데모
   ## 설치 방법 (Getting Started)
   ## 사용법 (Usage)
   ## 프로젝트 구조 (선택)
   ## 로드맵 (선택)
   ## 기여하기 (Contributing)
   ## 라이선스 (License)
   ## 크레딧 / 감사 (Acknowledgments)
   ```

   **뱃지 자동 생성 규칙:**
   - 필수: License (`img.shields.io/github/license/{owner}/{repo}`)
   - 필수: Version/Release (`img.shields.io/github/v/release/{owner}/{repo}`)
   - 권장: CI status (`img.shields.io/github/actions/workflow/status/{owner}/{repo}/ci.yml`)
   - 권장: Stars (`img.shields.io/github/stars/{owner}/{repo}`)
   - 선택: Built With 뱃지 그리드 (감지된 기술 스택별)

   **기술 스택 자동 감지 → Built With 뱃지:**

   | 감지 파일 | 뱃지 |
   |----------|------|
   | `package.json` | Node.js, (+ React/Next.js/Vue 등 deps에서 감지) |
   | `requirements.txt` / `pyproject.toml` | Python, (+ FastAPI/Django/Flask 등) |
   | `go.mod` | Go |
   | `Cargo.toml` | Rust |
   | `docker-compose.yml` / `Dockerfile` | Docker |
   | `*.ts` / `tsconfig.json` | TypeScript |

   **Social Preview 생성 (2가지 방식):**
   - 빠른 방법: `https://socialify.git.ci/{owner}/{repo}/image?theme=Dark&language=1&stargazers=1&forks=1` URL 생성
   - 커스텀: Pencil MCP 사용 가능 시 브랜드 이미지 직접 제작 (1280x640)

   **프로젝트 구조 트리 자동 생성:**
   - 주요 디렉토리/파일만 포함 (node_modules, __pycache__ 등 제외)
   - 각 디렉토리에 한 줄 설명 주석

   **기여자 테이블 (all-contributors 패턴):**
   - `git log --format='%aN'` 에서 기여자 추출
   - GitHub 프로필 링크 + 아바타 테이블 생성

   **Markdownlint 설정 자동 생성 (CI 린트 충돌 방지):**

   CI에 markdownlint를 추가할 때 `.markdownlint-cli2.jsonc`를 함께 생성한다.
   한국어 문서와 Keep a Changelog 형식에서 반복적으로 충돌하는 룰을 사전 비활성화:

   ```json
   {
     "config": {
       "MD013": false,
       "MD022": false,
       "MD024": false,
       "MD029": false,
       "MD031": false,
       "MD032": false,
       "MD033": false,
       "MD034": false,
       "MD040": false,
       "MD041": false,
       "MD050": false
     }
   }
   ```

   | 룰 | 비활성화 이유 |
   |----|-------------|
   | MD013 | 한국어 문장은 영어보다 줄 길이가 길어지기 쉬움 |
   | MD022, MD032 | 한국어 문서의 빈 줄 스타일이 영어와 다름 |
   | MD024 | CHANGELOG에서 `### Added` 등 섹션 제목 반복 필수 |
   | MD029 | 순서 목록 번호 스타일 (1. 1. 1. vs 1. 2. 3.) |
   | MD031 | 코드 블록 주변 빈 줄 스타일 |
   | MD033 | README에 HTML 태그 사용 (`<p align="center">` 뱃지 등) |
   | MD034 | 본문 내 bare URL (크레딧/링크 섹션에서 흔함) |
   | MD040 | 코드 블록 언어 미지정 (설명용 블록에선 불필요) |
   | MD041 | 첫 줄이 `<p align>` HTML일 때 제목 아님 오탐 |
   | MD050 | `__/10` 같은 패턴이 강조 문법으로 오인 |

   **자동 감지 규칙:**
   - 프로젝트의 주 언어 감지 → .gitignore 템플릿 맞춤
   - 한국어 프로젝트면 한국어로, 영어면 영어로 생성
   - 기존 README 구조를 최대한 유지하면서 누락 섹션만 추가

4. **RELEASE** — Git tag + GitHub Release 자동 생성
   - CHANGELOG.md 생성/업데이트 (Keep a Changelog 형식)
   - `git tag v{version}` + `git push --tags`
   - `gh release create` 로 GitHub Release 생성 (CHANGELOG에서 노트 추출)
   - (선택) git-cliff 설정 추가로 이후 릴리스 자동화

5. **VERIFY** — 최종 체크리스트 + 점수 확인

   ```
   [파일 존재]
   [ ] README.md (뱃지 + TOC + 히어로)
   [ ] .gitignore
   [ ] LICENSE
   [ ] CHANGELOG.md
   [ ] CONTRIBUTING.md
   [ ] CODE_OF_CONDUCT.md
   [ ] SECURITY.md
   [ ] .github/ISSUE_TEMPLATE/ (bug + feature)
   [ ] .github/PULL_REQUEST_TEMPLATE.md
   [ ] .github/workflows/ci.yml
   [ ] .markdownlint-cli2.jsonc (CI 린트 충돌 방지 설정)
   [ ] Social preview 이미지 또는 socialify URL

   [GitHub API 확인]
   [ ] gh api repos/{owner}/{repo}/community/profile → health_percentage: 100
   [ ] gh api repos/{owner}/{repo} → description, topics, homepage 설정됨
   [ ] Git tag 존재 + GitHub Release 존재

   [README 점수]
   [ ] 히어로 섹션 (센터 정렬) ✓
   [ ] 뱃지 2개 이상 ✓
   [ ] TOC ✓
   [ ] 설치 방법 (코드 블록) ✓
   [ ] 사용법/예제 ✓
   [ ] 라이선스 명시 ✓
   [ ] 최종 점수: __/10
   ```

   **Repo description + topics 자동 설정:**
   - `gh api repos/{owner}/{repo} -X PATCH -f description="..."` 로 About 섹션
   - `gh api repos/{owner}/{repo}/topics -X PUT` 로 토픽 태그 추가
