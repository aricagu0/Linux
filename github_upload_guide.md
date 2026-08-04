# 🚀 Ubuntu에서 Git & GitHub 사용법 및 업로드 완벽 가이드

우분투(Ubuntu) 환경에서 Git 설치부터 저장소(Repository) 생성, 개인 액세스 토큰(PAT) 인증, 비밀번호 자동 저장, 그리고 파일 업데이트까지의 전체 과정을 정리한 종합 가이드 문서입니다.

---

## 📑 목차
1. [최초 환경 설정 (Git 설치 & 사용자 등록)](#1-최초-환경-설정-git-설치--사용자-등록)
2. [로컬 저장소 폴더 생성 & Git 초기화](#2-로컬-저장소-폴더-생성--git-초기화)
3. [파일 생성, 스테이징 & 커밋 (Commit)](#3-파일-생성-스테이징--커밋-commit)
4. [GitHub 원격 저장소 연결 & 최초 Push](#4-github-원격-저장소-연결--최초-push)
5. [GitHub 개인 액세스 토큰(PAT) 발급 방법](#5-github-개인-액세스-토큰pat-발급-방법)
6. [비밀번호/토큰 자동 저장 설정 (Credential Helper)](#6-비밀번호토큰-자동-저장-설정-credential-helper)
7. [일상적인 파일 수정 및 업데이트 3단계](#7-일상적인-파일-수정-및-업데이트-3단계)
8. [자주 발생하는 문제 및 해결 방법 (Troubleshooting)](#8-자주-발생하는-문제-및-해결-방법-troubleshooting)

---

## 1. 최초 환경 설정 (Git 설치 & 사용자 등록)

터미널에서 `git` 프로그램을 설치하고 커밋 기록에 표기될 본인 깃허브 계정 정보를 등록합니다.

```bash
# 1-1. git 프로그램 설치
sudo apt update && sudo apt install -y git

# 1-2. git 사용자 이름 설정 (본인 깃허브 닉네임 입력)
git config --global user.name "aricagu0"

# 1-3. git 이메일 설정 (본인 깃허브 계정 이메일 입력)
git config --global user.email "본인이메일@example.com"
```

---

## 2. 로컬 저장소 폴더 생성 & Git 초기화

내 계정 홈 디렉토리에 작업할 폴더를 새로 만들고 Git 관리 대상으로 등록합니다.

```bash
# 2-1. 홈 디렉토리로 이동
cd ~

# 2-2. Linux 라는 이름의 작업 폴더 생성
mkdir Linux

# 2-3. 만들어진 Linux 폴더 안으로 이동
cd Linux

# 2-4. 이 폴더를 Git 저장소로 초기화
git init
```

---

## 3. 파일 생성, 스테이징 & 커밋 (Commit)

저장소 안에 파일을 만들고 Git 시스템에 기록합니다.

```bash
# 3-1. 예시 마크다운 또는 소스코드 파일 생성/편집
gedit README.md

# 3-2. 새로 만들거나 수정된 파일 전체를 Git 추적 대상(Staging Area)에 추가
git add .

# 3-3. 커밋 메시지와 함께 내 로컬 Git 데이터베이스에 저장
git commit -m "docs: add README file"

# 3-4. 기본 브랜치 이름을 main 으로 변경
git branch -M main
```

---

## 4. GitHub 원격 저장소 연결 & 최초 Push

내 컴퓨터의 local 폴더와 GitHub 웹사이트의 remote 저장소를 연결하고 푸시합니다.

```bash
# 4-1. 깃허브 원격 저장소 주소 연결 (origin 지정)
git remote add origin https://github.com/aricagu0/Linux.git

# 4-2. 깃허브로 최종 업로드 (기본 브랜치 세팅)
git push -u origin main
```

---

## 5. GitHub 개인 액세스 토큰(PAT) 발급 방법

GitHub 보안 정책상 일반 비밀번호 대신 **Personal Access Token (classic)**을 사용해야 합니다.

1. **GitHub 로그인** ➔ 오른쪽 상단 프로필 클릭 ➔ **[Settings]** 선택
2. 왼쪽 메뉴 맨 아래 **[Developer settings]** 클릭
3. **[Personal access tokens]** ➔ **[Tokens (classic)]** 클릭
4. **[Generate new token (classic)]** 버튼 클릭
5. **Note**: 토큰 이름 입력 (예: `ubuntu-pc`)
6. **Expiration**: `No expiration` (기한 없음) 또는 `90 days` 선택
7. **Select scopes**: 맨 위의 **`repo`** 체크박스 체크 (저장소 접근 전체 권한)
8. 맨 아래 **[Generate token]** 클릭 후 생성된 **`ghp_...` 형태의 토큰 문자열 복사!**

---

## 6. 비밀번호/토큰 자동 저장 설정 (Credential Helper)

매번 `git push`를 할 때마다 아이디와 토큰을 입력해야 하는 번거로움을 없애는 방법입니다.

```bash
# 토큰 영구 자동 저장 기능 활성화 (단 한 번만 실행)
git config --global credential.helper store
```
* 위 명령어를 실행하고 다음 `git push` 때 아이디와 토큰을 **마지막으로 딱 한 번만 입력**하면 컴퓨터 내부에 안전하게 기록되어 **이후부터는 0초 만에 로그인 없이 자동 푸시**됩니다!

---

## 7. 일상적인 파일 수정 및 업데이트 3단계

앞으로 새 코드를 작성하거나 파일을 수정한 후 깃허브에 올릴 때는 아래 **3단계 명령어**만 실행하면 됩니다.

```bash
# 1단계: 변경사항 전체 스테이징
git add .

# 2단계: 커밋 메시지 작성
git commit -m "feat: update ros2 notes and code"

# 3단계: 깃허브에 전송! (자동 로그인 적용됨)
git push
```

---

## 8. 자주 발생하는 문제 및 해결 방법 (Troubleshooting)

### Q1. `git push` 시 `Updates were rejected because the remote contains work...` 에러 발생 시
* **원인**: 깃허브 웹상에 먼저 생성된 파일(예: README)과 로컬 히스토리가 달라 발생.
* **해결법**: 최초 1회에 한해 강제 푸시 실행
  ```bash
  git push -u origin main --force
  ```

### Q2. 원격 저장소 URL을 잘못 등록했거나 변경하고 싶을 때
* **해결법**:
  ```bash
  git remote set-url origin https://github.com/aricagu0/Linux.git
  ```
