# 기여 가이드

Comad Voice에 기여해주셔서 감사합니다!

## 기여 방법

### 버그 리포트

[Issue 탭](https://github.com/kinkos1234/comad-voice/issues/new/choose)에서 "Bug Report"를 선택하고 양식을 채워주세요.

### 기능 제안

같은 [Issue 탭](https://github.com/kinkos1234/comad-voice/issues/new/choose)에서 "Feature Request"를 선택해주세요.

### 코드 기여

1. 이 레포를 Fork합니다
2. 새 브랜치를 만듭니다: `git checkout -b feature/내-기능`
3. 변경사항을 커밋합니다: `git commit -m "feat: 새 기능 추가"`
4. Push합니다: `git push origin feature/내-기능`
5. Pull Request를 생성합니다

### 커밋 메시지 규칙

```
feat: 새 기능 추가
fix: 버그 수정
docs: 문서 수정
style: 코드 포맷팅
refactor: 리팩토링
```

## 개발 환경 설정

```bash
git clone https://github.com/kinkos1234/comad-voice.git
cd comad-voice
```

주요 파일:
- `core/comad-voice.md` — 핵심 설정 (CLAUDE.md에 추가되는 내용)
- `install.sh` — 설치 스크립트
- `memory-templates/` — 메모리 템플릿
- `examples/` — 사용 예제

## 행동 강령

이 프로젝트는 [Contributor Covenant](CODE_OF_CONDUCT.md)를 따릅니다.
모든 참여자는 존중과 배려의 태도를 유지해주세요.

## 라이선스

기여한 코드는 [MIT 라이선스](LICENSE)에 따라 배포됩니다.
