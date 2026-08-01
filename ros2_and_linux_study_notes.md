# ROS 2 & Linux 개념 및 실습 총정리 노트

본 문서는 ROS 2 환경 설정 스크립트 분석부터 빌드 시스템, 키보드 비동기 입력을 처리하는 파이썬 코드, 리눅스 설정 및 Git/GitHub 연동까지의 질의응답 및 실습 내용을 종합 정리한 학습 노트입니다.

---

## 📑 목차
1. [ROS 2 setup.bash 스크립트 심층 분석](#1-ros-2-setupbash-스크립트-심층-분석)
2. [setup.bash vs local_setup.bash 의 차이점 및 존재 이유](#2-setupbash-vs-local_setupbash-의-차이점-및-존재-이유)
3. [ROS 2 스크립트 3대장 핵심 비교](#3-ros-2-스크립트-3대장-핵심-비교)
4. [colcon 빌드 메커니즘 및 주의사항](#4-colcon-빌드-메커니즘-및-주의사항)
5. [파이썬 키보드 비동기 입력 코드 (Getchar) 해설](#5-파이썬-키보드-비동기-입력-코드-getchar-해설)
6. [리눅스(Ubuntu) 유용한 팁 및 터미널 사용법](#6-리눅스ubuntu-유용한-팁-및-터미널-사용법)
7. [Git & GitHub 최초 생성 및 업로드 실습 가이드](#7-git--github-최초-생성-및-업로드-실습-가이드)

---

## 1. ROS 2 setup.bash 스크립트 심층 분석

### 💻 스크립트 소스 코드
```bash
# copied from ament_package/template/prefix_level/setup.bash

AMENT_SHELL=bash

# source setup.sh from same directory as this file
AMENT_CURRENT_PREFIX=$(builtin cd "`dirname "${BASH_SOURCE[0]}"`" && pwd)
# trace output
if [ -n "$AMENT_TRACE_SETUP_FILES" ]; then
  echo "# . \"$AMENT_CURRENT_PREFIX/setup.sh\""
fi
. "$AMENT_CURRENT_PREFIX/setup.sh"
```

### 🔍 줄별 상세 해석
* `AMENT_SHELL=bash`: 현재 사용하는 셸이 `bash`임을 지정하여 내부 ament 스크립트가 셸 전용 구문을 안전하게 구동하게 함.
* `AMENT_CURRENT_PREFIX=$(builtin cd "`dirname "${BASH_SOURCE[0]}"`" && pwd)`:
  * `${BASH_SOURCE[0]}`: 현재 실행 중인 파일 자신.
  * `dirname`: 디렉토리 경로만 추출.
  * `builtin cd ... && pwd`: 현재 파일이 위치한 디렉토리의 절대 경로를 안전하게 구해 `AMENT_CURRENT_PREFIX` 변수에 저장.
* `if [ -n "$AMENT_TRACE_SETUP_FILES" ]; then ... fi`: 환경변수 추적/디버깅 옵션이 켜져 있을 때 실행할 `setup.sh` 경로를 디버그 로그로 출력.
* `. "$AMENT_CURRENT_PREFIX/setup.sh"`: 같은 위치의 공통 `setup.sh` 환경 설정 파일을 현재 셸 세션으로 로드(source).

### ❓ 현재 디렉토리 위치를 동적으로 계산하는 이유
1. **터미널 실행 위치 독립성**: 사용자가 어느 폴더(예: `~`, `/tmp`)에 있든 `source /path/to/setup.bash`를 실행했을 때 자기 자신 파일 주변의 하위 스크립트(`setup.sh`)를 정확히 찾아내기 위함.
2. **이식성 (Relocatability)**: 워크스페이스 폴더 위치가 바뀌어도 하드코딩된 절대 경로 없이 옮겨진 위치 기준으로 환경 변수를 자동 계산함.
3. **상대적 환경변수 구성**: `$AMENT_CURRENT_PREFIX/bin`, `$AMENT_CURRENT_PREFIX/lib` 등 실행 파일과 라이브러리 경로를 `PATH`, `LD_LIBRARY_PATH`, `PYTHONPATH`에 주입하기 위함.

---

## 2. setup.bash vs local_setup.bash 의 차이점 및 존재 이유

### 📊 기본 개념 차이
* **`local_setup.bash`**: 현재 워크스페이스(또는 개별 패키지) 환경 변수만 단독 등록. (상위 환경은 건드리지 않음)
* **`setup.bash`**: 상위/부모 워크스페이스(예: `/opt/ros/humble`)까지 알아서 연쇄(Chain)로 전부 불러옴.

### ❓ setup.bash가 다 포괄하는데 local_setup.bash가 왜 따로 필요한가?
1. **중복 로딩 및 속도 저하 방지**: 이미 `.bashrc` 등에서 상위 ROS 2 환경을 불러온 상태라면, `local_setup.bash`만 로드하여 0.1초 만에 깔끔하게 내 경로만 갱신할 수 있음.
2. **빌드 도구(`colcon`)의 정교한 독립 환경 구성**: `colcon`이 수많은 패키지를 순서대로 빌드할 때 환경이 꼬이지 않도록 독립적인 부품 단위로 조작하기 위함.
3. **모듈화 디자인**: `setup.bash`는 "상위 환경 로드 + `local_setup.bash` 실행" 구조로 조립된 합성품이며, `local_setup.bash`가 기본 부품 역할을 수행함.

---

## 3. ROS 2 스크립트 3대장 핵심 비교

| 구분 | 1. `source /opt/ros/humble/setup.bash` | 2. `source ~/robot_ws/install/local_setup.bash` | 3. `source ~/robot_ws/install/setup.bash` |
| :--- | :--- | :--- | :--- |
| **불러오는 대상** | **순정 ROS 2 (기본 시스템)** | **내가 만든 코드/패키지만** | **기본 ROS 2 + 내가 만든 코드 둘 다** |
| **비유** | 📱 공장 출고 순정 OS | 🧩 내가 추가한 조각/모듈 | 📱+🧩 모든 앱이 활성화된 내 스마트폰 |
| **기본 ROS 명령어** | ⭕ 가능 | ❌ 불가능 (미로드 시) | ⭕ 가능 |
| **내가 만든 패키지** | ❌ **인식 불가** | ⭕ 가능 | ⭕ **가능** |
| **권장 사용법** | ROS 2 기본 툴만 쓸 때 | 상위 환경이 켜진 상태에서 갱신 시 | **일반 터미널 작업 시 (★ 제일 추천)** |

---

## 4. colcon 빌드 메커니즘 및 주의사항

### ⏱️ 파일 생성 시점 및 위치
* **생성 시점**: `colcon build` 명령어가 끝나는 순간 자동 생성.
* **생성 위치**: `~/robot_ws/install/` 디렉토리 내부.

### 🔄 증분 빌드 (Incremental Build)
* `colcon build`는 전체를 매번 다 빌드하지 않고, **수정된 파일 및 수정된 패키지만 감지**하여 빠르게 다시 빌드함.
* **특정 패키지만 빌드**: `colcon build --packages-select <패키지명>`
* **파이썬 개발 팁**: `colcon build --symlink-install` 옵션을 주면 파이썬 코드 수정 후 다시 빌드 안 해도 바로 적용됨.

### ⚠️ 주의사항: `src` 내부에서 빌드하면 안 되는 이유
* **원인**: `cd ~/robot_ws/src` 안에서 `colcon build`를 치면 `src` 폴더가 워크스페이스 루트로 오해되어 `src/build`, `src/install`, `src/log`가 생성됨.
* **문제점**: 소스 코드 디렉토리가 더러워지고, 다음 빌드 시 이전 결과물을 중복 탐색하여 에러 발생.
* **해결법**: `src/` 내부의 `build`, `install`, `log` 폴더를 삭제하고 반드시 상위 디렉토리(`~/robot_ws`)로 이동 후 `colcon build` 실행.

---

## 5. 파이썬 키보드 비동기 입력 코드 (Getchar) 해설

### 💻 소스 코드
```python
import os, time, sys, termios, atexit, tty
from select import select

class Getchar:
    def __init__(self):
        self.fd = sys.stdin.fileno()
        self.new_term = termios.tcgetattr(self.fd)
        self.old_term = termios.tcgetattr(self.fd)
  
        # 터미널 버퍼링(Enter 대기) 및 화면 출력(ECHO) 끄기
        self.new_term[3] = (self.new_term[3] & ~termios.ICANON & ~termios.ECHO)
        termios.tcsetattr(self.fd, termios.TCSAFLUSH, self.new_term)
  
        # 종료 시 터미널 복원 자동 등록
        atexit.register(self.set_normal_term)      
      
    def set_normal_term(self):
        termios.tcsetattr(self.fd, termios.TCSAFLUSH, self.old_term)
  
    def getch(self):
        return sys.stdin.read(1)
  
    def chk_stdin(self):
        # select를 사용하여 0초 대기(Non-blocking)로 입력 여부 검사
        dr, dw, de = select([sys.stdin], [], [], 0)
        return dr
```

### 🔍 핵심 포인트
1. `~termios.ICANON`: 엔터 키를 누르지 않아도 키 입력을 즉시 읽음.
2. `~termios.ECHO`: 누른 키가 터미널 화면에 글자로 보이지 않도록 감춤.
3. `select([sys.stdin], [], [], 0)`: 프로그램 루프가 키 입력을 기다리며 멈추지(Blocking) 않고, 0초 만에 키 입력 존재 여부만 체크해 비동기 제어 가능.
4. `atexit.register(...)`: 프로그램이 `Ctrl+C` 등으로 종료될 때 원래 터미널 환경으로 자동 원상복구.

---

## 6. 리눅스(Ubuntu) 유용한 팁 및 터미널 사용법

### 🖥️ Terminator(터미네이터) 화면 분할 단축키
* **좌우 분할**: `Ctrl` + `Shift` + `E`
* **상하 분할**: `Ctrl` + `Shift` + `O`
* **분할 창 이동**: `Alt` + `방향키 (← ↑ ↓ →)`
* **현재 분할 창 닫기**: `Ctrl` + `Shift` + `W`

### ⚙️ 화면 자동 꺼짐/잠금(화면 보호모드) 해제
```bash
# 1. 화면 꺼짐 디스플레이 대기시간 끄기 (0 = 안 끔)
gsettings set org.gnome.desktop.session idle-delay 0

# 2. 자동 화면 잠금 기능 끄기
gsettings set org.gnome.desktop.screensaver lock-enabled false
```

### 📄 source ~/.bashrc vs source /opt/ros/humble/setup.bash
* `source ~/.bashrc`: 터미널 전체 개인 설정(단축키, 프롬프트, 환경변수 등)을 처음부터 새로고침. (`.bashrc` 안에 ROS 2 설정 구문이 포함되어 있음)
* `source /opt/ros/humble/setup.bash`: 순정 ROS 2 전용 환경 변수만 단독 로드.

---

## 7. Git & GitHub 최초 생성 및 업로드 실습 가이드

우분투 내 PC에서 아예 처음부터 폴더를 만들고 깃허브에 첫 올리기까지의 5단계 과정입니다.

### 1단계: Git 설치 및 내 계정 설정
```bash
sudo apt update && sudo apt install -y git
git config --global user.name "aricagu0"
git config --global user.email "본인이메일@example.com"
```

### 2단계: 새 로컬 저장소 생성
```bash
cd ~
mkdir Linux
cd Linux
git init
```

### 3단계: 파일 작성
```bash
gedit 파일명.md
# 내용 작성 후 저장 및 닫기
```

### 4단계: 커밋하기
```bash
git add .
git commit -m "docs: add notes"
git branch -M main
```

### 5단계: 깃허브 연결 및 푸시
```bash
git remote add origin https://github.com/aricagu0/Linux.git
git push -u origin main --force
```

> **🔑 인증 시 주의사항**: Password에 일반 깃허브 비밀번호를 치면 안 되고, 깃허브 웹사이트 `Settings -> Developer settings -> Personal access tokens (classic)` 에서 생성한 **개인 토큰(`ghp_...`)**을 붙여넣어야 푸시가 성공함.

### 🔄 향후 파일 수정 후 깃허브 업데이트 3단계
```bash
git add .
git commit -m "수정 내용 메모"
git push
```
