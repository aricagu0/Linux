# ROS 2 colcon 명령어 자동 완성(argcomplete) 가이드

ROS 2 빌드 도구인 `colcon` 명령어를 사용할 때 터미널에서 **<kbd>Tab</kbd> 키로 명령어, 옵션, 패키지 이름을 자동 완성**시켜주는 `colcon-argcomplete` 스크립트 활용 가이드입니다.

---

## 📌 한눈에 보는 핵심 기능

* **명령어**: `source /usr/share/colcon_argcomplete/hook/colcon-argcomplete.bash`
* **역할**: 터미널 셸(Shell)에 `colcon` 전용 오토 컴플리션(Auto-completion) 기능을 주입함.
* **장점**: 길고 복잡한 옵션 명칭이나 패키지 오타 방지 및 개발 속도 대폭 향상.

---

## 💡 주요 자동 완성 활용 예시

### 1. 하위 명령어 자동 추천
```bash
colcon [Tab][Tab]
# 출력: build  test  list  graph  info  test-result ...
```

### 2. 빌드 옵션 자동 완성
```bash
colcon build --sy[Tab]
# 자동 완성 -> colcon build --symlink-install
```

### 3. 내 패키지 이름 자동 추천 (★ 가장 유용)
```bash
colcon build --packages-select [Tab]
# 출력: py_pubsub  ros_tutorials  turtle_pkg ... (src/ 안의 내 패키지 자동 목록화)
```

---

## 🛠️ 영구 등록 방법 (`~/.bashrc`)

새 터미널을 열 때마다 자동으로 적용되도록 `~/.bashrc` 파일 맨 밑에 추가합니다.

```bash
# 1. ~/.bashrc 파일 맨 밑에 등록
echo "source /usr/share/colcon_argcomplete/hook/colcon-argcomplete.bash" >> ~/.bashrc

# 2. 변경 사항 즉시 적용
source ~/.bashrc
```
