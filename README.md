# Ver4 — SWP Shipyard 재구축 키트

Ver3 완성본(명세 이후 추가 기능 포함)을 **명세·참고 이미지·시드만으로** 처음부터 다시 만들기 위한 폴더다. 앱 코드는 들어 있지 않다.

## 시작

```bash
scripts/bootstrap.sh        # 최초 1회: Homebrew(동의 후)·uv·Python·Node·Ollama·의존성·Playwright·글꼴·Unity 점검/설치 (--check: 점검만)
scripts/setup-ollama.sh     # 로컬 LLM만 따로 준비할 때 (아래 절)
scripts/setup.sh            # 최초 1회: 환경 점검(node·uv·Chrome·Unity·Ollama·한글 글꼴), playwright 설치
scripts/start.sh            # 다음 phase 안내
scripts/start.sh --launch   # 새 Claude 세션에서 /build 실행 (phase 하나 끝나면 /exit 후 다시)
```

phase 6개(P1 백엔드1 → P2 백엔드2 → P3 화면1 → P4 화면2 → P5 챗봇 → P6 Unity·수용), 작업 30개. 세부는 `specs/index.md`, 작업 목록은 `state/tasks.json`.

## 로컬 LLM (Ollama)

챗봇의 일반 질문 답변은 이 Mac에서 도는 Ollama가 만든다(데이터 조회는 MCP, 모델과 무관). Ollama는 **시스템 공용**으로 설치하고, 프로젝트 안에는 실행 파일·모델을 두지 않는다.

| 설정 | 기본값 | 비고 |
| --- | --- | --- |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | 백엔드와 설치 스크립트가 함께 쓴다 |
| `OLLAMA_MODEL` | `qwen2.5:1.5b-instruct` | 약 1GB. 바꾸려면 환경 변수 또는 `backend/.env`에 지정 |

### 최초 설치 (자동)

```bash
scripts/setup-ollama.sh           # 없으면 설치·시작·다운로드, 있으면 건너뛰고 추론까지 검증
scripts/setup-ollama.sh --check   # 아무것도 바꾸지 않고 상태만 점검 (실패하면 exit 1)
OLLAMA_MODEL=qwen2.5:3b-instruct scripts/setup-ollama.sh   # 다른 모델로 준비
```

순서: macOS 확인 → `ollama` 명령 확인(없으면 Homebrew로 `brew install ollama`, Homebrew가 없으면 설치 방법만 안내하고 멈춤) → `GET /api/tags`로 서버 확인(실행 중이면 그대로 사용, 없으면 `ollama serve`를 백그라운드로 시작) → 모델 확인(없으면 `ollama pull`) → `POST /api/chat` 실제 추론. 반복 실행해도 재설치·재시작·재다운로드하지 않고, 실행 중인 서버를 끄지 않는다.

### 수동 설치·운영

```bash
brew install ollama                          # 설치 (Homebrew 필요)
ollama --version                             # 버전 확인

ollama serve                                 # 서버 시작(이 터미널에서 실행, Ctrl+C로 종료)
brew services start ollama                   # 또는 로그인 시 자동 시작 서비스로 등록
brew services stop ollama                    # 서비스 종료
kill "$(cat state/run/ollama-serve.pid)"     # setup-ollama.sh가 띄운 서버 종료

ollama pull qwen2.5:1.5b-instruct            # 모델 다운로드
ollama list                                  # 설치된 모델 목록
curl -s http://127.0.0.1:11434/api/tags      # 서버가 보고 있는 모델 목록(API)
ollama rm <모델>                              # 모델 삭제
```

`setup-ollama.sh`가 서버를 띄웠을 때 로그는 `state/run/ollama-serve.log`, PID는 `state/run/ollama-serve.pid`.

### 자주 발생하는 오류

| 증상 | 원인과 해결 |
| --- | --- |
| `ollama: command not found` | 설치되지 않았거나 PATH에 `/opt/homebrew/bin`이 없다. `scripts/setup-ollama.sh` 실행 또는 `eval "$(/opt/homebrew/bin/brew shellenv)"` 후 새 터미널 |
| 스크립트가 `Homebrew 없음`으로 멈춤 | 의도된 동작. 안내된 Homebrew 설치 명령을 직접 실행하거나 https://ollama.com/download 의 앱을 설치한 뒤 다시 실행 |
| `Error: listen tcp 127.0.0.1:11434: bind: address already in use` | 다른 Ollama 서버가 이미 실행 중이다. 그 서버를 쓰면 된다(스크립트는 자동으로 재사용). 다른 포트가 필요하면 `OLLAMA_BASE_URL=http://127.0.0.1:11435` |
| 챗봇 `로컬 모델에 연결할 수 없습니다` (503 CHAT_OFFLINE) | 서버가 꺼져 있다. `scripts/setup-ollama.sh` 또는 `ollama serve` |
| 챗봇 `로컬 채팅 모델을 찾을 수 없습니다` (503 CHAT_MODEL_MISSING) | 서버에 `OLLAMA_MODEL` 모델이 없다. `ollama pull <모델>` 후 `ollama list`로 확인 |
| `ollama list`에는 있는데 챗봇이 모델 없음 | CLI와 백엔드가 서로 다른 서버를 본다. `OLLAMA_HOST`(CLI)와 `OLLAMA_BASE_URL`(백엔드)을 같은 주소로 |
| 모델 다운로드 실패·중단 | 네트워크·디스크(약 1GB) 확인 후 같은 명령 재실행(이어받기) |
| 첫 답변이 수십 초 걸림 | 첫 요청에 모델을 메모리에 올린다. 두 번째부터 빨라진다 |
| 답변이 부정확함 | 1.5B 소형 모델의 한계. `OLLAMA_MODEL`로 더 큰 모델을 지정할 수 있다(메모리·속도 고려) |

## 폴더

| 경로 | 내용 |
| --- | --- |
| `specs/` | 기반·데이터 모델·규칙·디자인 + 기능 명세 F01~F16 (F11 사용 로그, F12 건의·문의, F13 챗봇·MCP·LLM, F14 보고서, F15 매뉴얼, F16 예시 데이터·데모) |
| `reference/ui/` | 1440x900 기준 화면 44장(원본 + 2026-11-13 최신), `README.md`에 촬영 상태 |
| `reference/manual/` | 매뉴얼 예시 사진 10장(앱 자산으로 복사) |
| `reference/seed/seed.json` | 초기 데이터(메뉴 13개 포함) |
| `scripts/` | 워크플로(작업 선택·검증·서버·브라우저 캡처·GIF) — 앱 코드 아님 |
| `.claude/skills/build` | `/build`: 한 세션 = 한 phase |
| `config/` | 실행 명령·환경 점검·예산 |

## 토큰을 아끼는 설계

- **판단 없는 일은 스크립트로**: 다음 작업 선택·완료 판정·검증 요약·서버 관리·화면 캡처를 스크립트가 한다. 세션은 `start.sh claim` 출력 하나로 이번 phase의 작업·명세·이미지를 받는다.
- **한 phase = 한 세션**: 컨텍스트가 커지기 전에 끊는다. 인계는 `PROGRESS.md` 40줄 + 자동 생성 `SOURCEMAP.md`(API 계약·컴포넌트 목록).
- **한 요구사항 = 한 곳**: 추가 기능을 별도 변경 문서로 두지 않고 해당 F 명세에 합쳤다. 작업마다 필요한 명세·이미지만 읽는다.
- **이미지는 작업별로만**: 30개 작업에 화면을 나눠 붙였다. 장당 약 1.7천 토큰.
- **시행착오 메모**: 이전 구현에서 실제로 막힌 것(글꼴 OS/2, OTP 재사용, 화면 밖 hover, MCP 환경 변수 등)을 `specs/index.md`에 적어 재시도를 줄인다.
- **예시 데이터는 생성 규칙으로**: 예시 PDF·사용 로그는 결과물을 넣지 않고 결정적 생성 규칙(F16, 난수 시드 고정)으로 둔다.

## 필요한 것

Node 20+, uv(Python 3.10+), Google Chrome, Unity 6000.x + Web Build Support(로그인·Personal 라이선스), 시스템 Ollama + `qwen2.5:1.5b-instruct`(`scripts/setup-ollama.sh`), macOS 한글 글꼴(또는 `SHIPYARD_REPORT_FONT`).
# ShipYard-Final
