# Comad Photo

> 사진 보정, 말만 해.

Claude Code + Photoshop MCP로 사진 보정을 자동화하는 에이전트.

## 작동 방식

1. 이미지를 보고 분석
2. 보정 방향을 카드로 제안
3. 선택하면 Photoshop에서 실행 (조정 레이어)
4. 결과 확인 → "더 따뜻하게" 같은 피드백 → 반복
5. "좋아" 하면 끝

## 설치

```bash
./install.sh
```

## 사용

```
"이 사진 보정해줘"
"더 밝게"
"좋아"
```

## 원칙

- **비파괴**: 조정 레이어만 사용, 원본 보존
- **최소 개입**: 필요한 보정만
- **사람이 판단**: AI는 제안, 미적 결정은 사용자

## Requirements

- Adobe Photoshop (running)
- Claude Code
- Node.js

## License

MIT
