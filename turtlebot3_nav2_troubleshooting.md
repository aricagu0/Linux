# TurtleBot3 Nav2 "Feedback: Aborted" 트러블슈팅 기록

**환경**
- 로봇: TurtleBot3 (Raspberry Pi 4, Ubuntu, ROS2)
- 원격 PC: Ubuntu, RViz2 + Nav2
- 통신: PC의 Wi-Fi 핫스팟(`10.42.0.0/24`)을 통해 라즈베리파이와 연결
- 날짜: 2026-08-10

---

## 1. 문제 상황

RViz2에서 Nav2 실행 후 목표(goal)로 주행 중 **Navigation 패널의 Feedback이 `aborted`**로 표시됨.

**스크린샷 관찰 사항**
- Navigation: `active`, Localization: `active`
- Feedback: `aborted` (빨간색)
- 코스트맵(inflation) 영역이 실제 벽보다 넓게 퍼져 보임
- 우측 Docking / Selector 패널에서 플러그인 로드 에러 발생
  ```
  class nav2_rviz_plugins/Docking with base class type rviz_common::Panel does not exist
  ```
  → RViz 설정 파일과 설치된 nav2_rviz_plugins 버전 불일치로 추정 (기능상 치명적이지 않음)

---

## 2. 1차 원인 분석 (가설)

Feedback aborted의 일반적 가능 원인으로 아래 4가지를 제시:
1. 로컬/글로벌 코스트맵 상에서 경로를 못 찾음 (장애물에 막힘)
2. 로봇이 costmap inflation 영역에 갇혀 recovery도 실패
3. goal 위치 자체가 코스트맵 상 occupied 영역에 찍힘
4. `controller_server`/`planner_server` 타임아웃

이 가설들을 확인하는 방법으로 다음을 안내:
- 터미널 로그 확인 (`planner_server`, `controller_server`, `bt_navigator` 관련 에러 메시지)
- RViz에서 Global/Local Costmap 레이어를 켜서 goal 및 경로가 막혔는지 시각 확인
- `ros2 action send_goal /navigate_to_pose ...` 로 직접 goal 전송 후 result의 error_code/error_msg 확인
- `ros2 topic echo /behavior_tree_log`, `ros2 topic hz /tf` 등으로 상태 점검

---

## 3. 실제 로그 확인 → 원인 특정

터미널 로그 캡처 결과, 실제 원인은 코스트맵 문제가 아니라 **TF(좌표 변환) Extrapolation 에러**로 확인됨.

```
[transformPoseInTargetFrame]: Extrapolation Error looking up target frame:
Lookup would require extrapolation into the past.
Requested time 1786331496.663599 but the earliest data is at time 1786331748.430921,
when looking up transform from frame [base_link] to frame [map]

[BehaviorTreeEngine]: Behavior Tree tick rate 100.00 was exceeded!
```

- `base_link → map` TF 요청 시각과 실제 버퍼상 시각의 차이가 **약 250초 이상** 벌어짐
- BT tick rate(100Hz) 초과 경고도 동반 → 시스템 전반의 타이밍 지연 신호

**결론: 원인은 장애물/코스트맵이 아니라 두 기기 간 시스템 시각 불일치(clock skew)**

---

## 4. 시간 동기화 상태 점검

### PC (`ros@ros`)
```
$ timedatectl
Universal time: 월 2026-08-10 03:28:20 UTC
System clock synchronized: yes
NTP service: active
```

### 라즈베리파이 (`pi@raspberrypi`)
```
$ timedatectl
Universal time: Mon 2026-08-10 03:28:12 UTC
System clock synchronized: yes
NTP service: active
```

**비교 결과**: `synchronized: yes`로 표시되지만 실제 UTC 시각 비교 시 **약 10~17초 차이** 확인. 각자 독립적으로 "동기화됨"이라고 표시될 뿐, 서로 같은 기준시를 공유하지 않는 상태였음.

### 네트워크 구성 확인 (PC, `ifconfig`)
| 인터페이스 | IP | 비고 |
|---|---|---|
| `eno1` (유선) | `10.10.10.64/24` | |
| `wlxfc221c204d1a` (Wi-Fi 핫스팟) | `10.42.0.1/24` | 당시 RX/TX 0, 트래픽 없음 |

### 라즈베리파이 네트워크 확인 (`ip addr show`)
```
wlan0: inet 10.42.0.39/24 ... (PC의 Wi-Fi 핫스팟에 연결됨)
```

→ **PC와 라즈베리파이는 `10.42.0.0/24` 대역으로 연결**되어 있음이 확인됨. PC IP `10.42.0.1`을 시간 기준으로 사용하기로 결정.

---

## 5. 해결 절차: chrony를 이용한 시간 동기화

### 5-1. PC를 로컬 NTP 마스터로 설정

기존 PC의 `chrony.conf`에 `server 10.10.10.64 iburst`(자기 자신을 가리킴)로 잘못 설정되어 있던 것을 발견 → 수정.

`/etc/chrony/chrony.conf` (PC):
```
# 기존 pool ntp.ubuntu.com 등은 주석 처리
# server 10.10.10.64 iburst   ← 삭제/주석 (자기 자신 참조 오류)
local stratum 10
allow 10.10.10.0/24
allow 10.42.0.0/24

sourcedir /run/chrony-dhcp
sourcedir /etc/chrony/sources.d
keyfile /etc/chrony/chrony.keys
driftfile /var/lib/chrony/chrony.drift
ntsdumpdir /var/lib/chrony
logdir /var/log/chrony
maxupdateskew 100.0
rtcsync
makestep 1 3
leapsectz right/UTC
```

```bash
sudo systemctl restart chrony
sudo chronyc tracking
```

결과:
```
Stratum         : 10
Reference ID    : 7F7F0101 ()   # 로컬 자체 기준시
Leap status     : Normal
```
→ PC가 네트워크의 시간 마스터로 정상 동작 확인.

### 5-2. 라즈베리파이 설정

**문제 발생**: 라즈베리파이에 `chrony` 자체가 설치되어 있지 않았음 (`Unit chrony.service could not be found`).

**설치**:
```bash
sudo apt update
sudo apt install chrony -y
```
- 설치 과정에서 기존 `systemd-timesyncd`가 자동 제거되어 충돌 문제 없이 정리됨.

**설정** (`/etc/chrony/chrony.conf`):
```
# 기존 pool ... 줄들 주석 처리
server 10.42.0.1 iburst prefer
```

```bash
sudo systemctl restart chrony
sudo systemctl enable chrony
```

### 5-3. 동기화 확인

```bash
sudo chronyc sources -v
```
```
MS Name/IP address         Stratum Poll Reach LastRx Last sample
===============================================================================
^* ros                          10   6    17    56   +461us[+9115us] +/- 2329us
```
- `^*`: PC(`ros`)를 최적 시간 소스로 선택하여 동기화 중
- 오차가 **마이크로초(μs) 단위**로 안정화됨 (기존 250초 차이 대비 극적으로 개선)

```bash
sudo chronyc tracking
```
```
Leap status: Normal
```
→ 정상 동기화 완료.

**`Leap status` 값 참고**
- `Normal`: 정상 (윤초 보정 예정 없음) ✅
- `Insert second` / `Delete second`: 윤초 보정 예정 (드묾, 문제 아님)
- `Not synchronised`: 아직 동기화 안 됨 ❌

---

## 6. 다음 단계 (검증 예정)

1. 양쪽 기기에서 동시에 `date +%s.%N` 실행하여 초 단위 오차 최종 확인
2. Nav2 관련 노드(로봇 bringup, RViz + Nav2) 재시작
3. 동일한 goal로 재테스트하여 아래 확인:
   - `Extrapolation Error` 재발 여부
   - `BehaviorTree tick rate 100.00 was exceeded!` 경고 빈도
   - Navigation 패널 Feedback이 `aborted` 대신 정상적으로 진행/성공하는지

만약 시간 동기화 후에도 aborted가 재발하면, 그때는 코스트맵/장애물(원래 1차 가설)이나 Wi-Fi 네트워크 지연 쪽을 추가로 점검 필요.

---

## 7. 참고: RViz Docking/Selector 패널 에러 (별도 이슈, 미해결)

```
class nav2_rviz_plugins/Docking with base class type rviz_common::Panel does not exist
class nav2_rviz_plugins/Selector with base class type rviz_common::Panel does not exist
```

- 원인: `.rviz` 설정 파일이 참조하는 패널 클래스와 현재 설치된 `nav2_rviz_plugins` 버전 간 불일치 (Nav2 버전 업데이트로 베이스 클래스가 변경됨)
- 영향: Navigation 기능 자체에는 영향 없음
- 조치 방법 (필요 시):
  - RViz `Panels` 메뉴에서 Docking/Selector 패널 제거 후 설정 재저장, 또는
  - `sudo apt update && sudo apt upgrade ros-<distro>-nav2-rviz-plugins`로 패키지 버전 일치
