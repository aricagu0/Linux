# TurtleBot3 Nav2 — 위치 추정(Localization) 불안정 & 주행 망설임 트러블슈팅 기록

**환경**
- 로봇: TurtleBot3 (Raspberry Pi 4, Ubuntu, ROS2 Humble)
- 원격 PC: Ubuntu, RViz2 + Nav2
- 통신: 여러 팀이 같은 네트워크(Wi-Fi)를 공유하는 실습/교육 환경
- 날짜: 2026-08-10 (이전 TF Extrapolation Error 트러블슈팅에 이어지는 후속 세션)

**전제 상황**: 이전 세션에서 시간 동기화(chrony) 문제를 해결하여 `Feedback: reached`까지는 성공했으나, 주행 중 로봇이 위치를 잘못 찾고 심하게 망설이는 새로운 증상 발생.

---

## 1. 증상 (스크린샷 관찰)

- Navigation: `active`, Localization: `active`, **Feedback: `reached`** (TF 문제는 해결된 상태)
- 그러나 주행 중 로봇이 **망설이며(진동하듯) 움직임**
- RViz 상 **AMCL 파티클(Amcl Particle Swarm)이 로봇 주변에 넓게 흩어져 있음** → 위치 추정이 한 점으로 수렴하지 못함
- 코스트맵 inflation(빨강/보라색 영역)이 실제 벽(하늘색 라인)보다 훨씬 넓게 퍼져 보임
- RViz 우측 Docking/Selector 패널 플러그인 로드 에러는 여전히 존재 (기능상 영향 없음, 별도 이슈)

### 1차 가설
1. AMCL 파라미터(`min_particles`/`max_particles`, `laser_max_range` 등) 문제로 위치 추정 불안정
2. Inflation 파라미터(`inflation_radius`, `cost_scaling_factor`) 과다로 통로가 좁게 인식되어 로컬 플래너가 진동
3. 지도(`map3.pgm`) 자체의 불완전한 스캔 영역

---

## 2. 지도 파일 분석

### `map3.yaml`
```yaml
image: map3.pgm
mode: trinary
resolution: 0.05
origin: [-3.6, -2.85, 0]
negate: 0
occupied_thresh: 0.65
free_thresh: 0.25
```
- 표준적인 값, 특별한 문제 없음.

### `map3.pgm` (이미지 확인)
- 크기 155×97px, 해상도 0.05m/px
- 벽 라인은 비교적 깔끔하게 그려져 있어 **코스트맵의 과도한 inflation은 지도 자체 문제가 아니라 런타임 파라미터 문제**로 판단
- 지도 왼쪽 아래에 삐죽 튀어나온 free-space 영역 발견 → SLAM 매핑 시 불완전하게 열린 구역으로, 이 부분이 AMCL 혼란의 요인이 될 수 있음(재매핑 권장 사항으로 언급)

---

## 3. nav2_params.yaml 분석 → 핵심 원인 발견

### 🚨 발견 1: `use_sim_time: True`가 거의 모든 섹션에 설정되어 있었음

실제 하드웨어(라즈베리파이 + 실물 로봇)로 구동 중인데, 파라미터 파일은 **시뮬레이션(Gazebo)용 설정**(`use_sim_time: True`)이 거의 전 노드(`amcl`, `bt_navigator`, `controller_server` 등)에 적용되어 있었음.

- `use_sim_time: True`이면 ROS2가 `/clock` 토픽에서 시간을 받으려 하는데, 실제 하드웨어 환경에는 `/clock`을 발행하는 시뮬레이터가 없어 시간 처리가 불안정해짐
- 지금까지 겪은 Extrapolation Error, AMCL 파티클 미수렴, 망설임 현상의 **근본 원인 후보**로 지목

### 조치: 시스템 경로 파일 수정 시도 → 권한 문제 → 사용자 경로로 복사 후 수정

```bash
# 최초 시도 (실패 - 시스템 경로 권한 문제)
cd /opt/ros/humble/share/nav2_bringup/params
sed -i 's/use_sim_time: True/use_sim_time: False/g' nav2_params.yaml
# sed: couldn't open temporary file ./sedysjJWN: Permission denied
```

```bash
# 해결: 사용자 워크스페이스로 복사 후 수정
mkdir -p ~/nav2_config
cp /opt/ros/humble/share/nav2_bringup/params/nav2_params.yaml ~/nav2_config/
sed -i 's/use_sim_time: True/use_sim_time: False/g' ~/nav2_config/nav2_params.yaml
```

**놓친 부분 발견**: `behavior_server` 섹션에는 소문자로 `use_sim_time: true`라고 되어 있어 대문자 기준 sed에 걸리지 않음 → 재검색으로 발견 후 추가 수정:
```bash
sed -i 's/use_sim_time: true/use_sim_time: False/g' ~/nav2_config/nav2_params.yaml
```
최종 확인: `grep "use_sim_time" ~/nav2_config/nav2_params.yaml` → 15줄 전부 `False` 확인.

### 발견 2: inflation_radius / cost_scaling_factor는 TB3 표준값
```yaml
inflation_layer:
  cost_scaling_factor: 3.0
  inflation_radius: 0.55
```
→ TurtleBot3 Nav2 예제 기본값과 동일. 문제라기보다 로봇 반지름(0.22m) + inflation(0.55m)이 겹쳐 좁은 통로에서 시각적으로 넓어 보이는 정상 범위로 판단. 필요시 `0.4` / `5.0` 정도로 미세 조정 가능하다고 안내.

### 발견 3: AMCL `laser_max_range: 100.0`
실제 라이다 스펙(약 3.5m)과 맞지 않는 값. 정합성 차원에서 `3.5`로 맞추는 것을 권장(필수는 아님).

---

## 4. 새 파라미터 파일 적용

### launch 인자 확인
```bash
ros2 launch turtlebot3_navigation2 navigation2.launch.py --show-args
```
`map`, `params_file`, `use_sim_time` 등의 인자 존재 확인.

### 재실행
```bash
ros2 launch turtlebot3_navigation2 navigation2.launch.py \
  map:=/home/ros/map3.yaml \
  params_file:=/home/ros/nav2_config/nav2_params.yaml \
  use_sim_time:=false
```

### 적용 검증
```bash
ros2 param get /amcl use_sim_time              # → False
ros2 param get /controller_server use_sim_time # → False
ros2 param get /behavior_server use_sim_time   # → Wait for service timed out (별도 이슈로 발전, 아래 5번 참조)
```

---

## 5. Lifecycle 상태 점검 → 두 번째 핵심 원인 발견

### 초기 점검에서 이상 발견
```bash
ros2 lifecycle get /behavior_server
# inactive [2]
```

전체 노드 순회 점검:
```bash
for node in /amcl /controller_server /planner_server /smoother_server /behavior_server \
  /bt_navigator /waypoint_follower /velocity_smoother /map_server \
  /global_costmap/global_costmap /local_costmap/local_costmap; do
  echo -n "$node: "; ros2 lifecycle get $node
done
```

**결과**:
| 노드 | 상태 |
|---|---|
| amcl, controller_server, smoother_server, map_server, local_costmap | active |
| **global_costmap/global_costmap** | **`activating [13]`** (전환 중 멈춤) |
| planner_server, behavior_server | 응답 없음(hang) |
| bt_navigator, waypoint_follower, velocity_smoother | `inactive` (activate 시도조차 못 함) |

→ `global_costmap`이 activating에서 멈추면서, 뒤이어 activate되어야 할 노드들이 순차적으로 막힌 상태로 진단.

### htop으로 리소스 확인 (라즈베리파이)
```
Mem: 270M/7.58G, CPU: 20%/5.9%/5.9%/5.4%
```
→ CPU/메모리는 전혀 부족하지 않음. 리소스 부족은 원인에서 배제.

### 🚨 발견: 동일 노드가 여러 개 중복 실행 중 (htop 프로세스 목록)
```
robot_state_publisher  ×8
turtlebot3_ros (/dev/ttyACM0)  ×7
single_coin_d4_node  ×7
turtlebot3_bringup robot.launch.py  ×4
```
- 여러 `turtlebot3_ros`가 동일 시리얼 포트(`/dev/ttyACM0`)에 동시 접근 시도 → 통신 불안정
- 여러 `robot_state_publisher`가 동일 TF를 중복 발행 → TF tree 충돌 가능성
- 원인 추정: launch를 여러 차례 실행하면서 이전 프로세스를 완전히 종료하지 않음 (터미널 강제 종료, SSH 재연결, 중복 실행 등)

### 조치 (정리 명령 안내)
```bash
pkill -f turtlebot3_bringup
pkill -f robot_state_publisher
pkill -f turtlebot3_ros
pkill -f single_coin_d4_node
```
이후 확인 시 라즈베리파이 프로세스는 각 노드당 1개씩만 남아 정상 상태로 확인됨:
```
1161 ros2 launch turtlebot3_bringup robot.launch.py
1163 robot_state_publisher
1165 single_coin_d4_node
1167 turtlebot3_ros -i /dev/ttyACM0
```

### 중복 프로세스 발생 원인 정리 (안내 사항)
1. `Ctrl+C`로 정상 종료하지 않고 터미널을 강제로 닫음
2. SSH 세션 끊김 시 launch 프로세스가 고아 프로세스로 잔존
3. 같은 launch 명령을 실수로 중복 실행
4. 자동 시작 스크립트(systemd/cron)와 수동 실행이 겹침

### 재발 방지 권장 사항
- 재실행 전 항상 `pkill -f ...`로 클린업
- `tmux`/`screen` 세션 내에서 launch 실행하여 SSH 끊김에도 세션 유지

---

## 6. 세 번째 핵심 원인: 초기 위치(2D Pose Estimate) 미설정

터미널 로그 캡처로 최종 원인 확인:
```
[global_costmap]: Timed out waiting for transform from base_link to map to become available,
tf error: Invalid frame ID "map" passed to canTransform argument target_frame - frame does not exist
[amcl]: AMCL cannot publish a pose or update the transform. Please set the initial pose...
```

**원인**: AMCL은 초기 위치(initial pose)를 받기 전까지 `map → odom` TF를 발행하지 않음 → `map` 프레임 자체가 존재하지 않아 `global_costmap`이 이를 기다리며 `activating`에 멈춰 있었음 → 이로 인해 뒤따르는 `planner_server`, `behavior_server`, `bt_navigator`, `waypoint_follower`, `velocity_smoother`까지 연쇄적으로 activate 지연/실패.

### 조치
RViz 툴바에서 **`2D Pose Estimate`**로 로봇의 실제 위치/방향을 지정.

### 결과 검증
```bash
ros2 lifecycle get /global_costmap/global_costmap
# active [3]

for node in /amcl /controller_server /planner_server /smoother_server /behavior_server \
  /bt_navigator /waypoint_follower /velocity_smoother /map_server \
  /global_costmap/global_costmap /local_costmap/local_costmap; do
  echo -n "$node: "; ros2 lifecycle get $node
done
```
**결과: 전체 노드 `active [3]` 확인 완료.** (`waypoint_follower` 조회 시 일시적으로 응답이 느려 보였으나 재확인 결과 `active [3]`로 정상.)

---

## 7. 네 번째 문제: `/scan` 메시지 큐 풀 & 지연 (남은 이슈)

Nav2 스택 activate 완료 후에도 아래 로그가 지속적으로 발생:

```
[amcl]: Message Filter dropping message: frame 'base_scan' ... reason 'discarding message because the queue is full'
[local_costmap]: Message Filter dropping message: frame 'base_scan' ... reason 'the timestamp on the message is earlier than all the data in the transform cache'
[global_costmap]: 위와 동일 사유
```

### 정량 확인
```bash
ros2 topic hz /scan
```
- 평균 rate: 약 10Hz (정상 스펙)
- **max 간격 0.701s**, std dev 0.11~0.16s → 발행 간격이 매우 불규칙

```bash
ros2 topic delay /scan
```
- 평균 지연: 0.15~0.5s
- **최대 지연 1.991초**, std dev 0.3~0.7s → 예측 불가능한 큰 지연 스파이크 존재

### 원인 결론
라이다 드라이버 자체는 정상(평균 10Hz)이나, **전송 과정에서 간헐적으로 최대 약 2초까지 지연되는 스파이크** 발생 → TF 캐시 윈도우를 초과하여 costmap/AMCL이 스캔 데이터를 버림 → 장애물 인식이 순간적으로 끊기면서 로봇이 판단을 반복(재계획)하는 것이 "망설임"으로 나타난 것으로 결론.

### 최종 확인된 근본 원인
> **여러 팀이 동시에 같은 Wi-Fi/네트워크 환경에서 각자의 ROS2 시스템을 운용 중** (교육/실습 환경 공유)

이로 인해:
- 여러 팀의 `/scan`, TF, odom 등 트래픽이 동일 대역폭을 두고 경쟁 → 지연·손실 증가
- ROS2 DDS 기본 멀티캐스트 discovery 트래픽이 팀 수만큼 증폭
- Wi-Fi 환경에서 멀티캐스트 폭주로 AP 부담 가중

---

## 8. 네트워크 공유 문제에 대한 권장 조치

### 1. `ROS_DOMAIN_ID` 팀별 분리 (최우선 권장)
```bash
export ROS_DOMAIN_ID=42   # 팀마다 다른 번호로, 0~101 범위 내
echo "export ROS_DOMAIN_ID=42" >> ~/.bashrc
source ~/.bashrc
```
PC와 라즈베리파이 양쪽에 **동일한 번호**로 설정해야 서로 통신 가능. 다른 팀과 겹치지 않게 조율 필요.

### 2. 팀별 AP/채널 분리 요청
가능하면 진행자 측에 팀별 AP 분리 또는 채널 분리를 요청.

### 3. 유선 연결 전환 (가장 확실한 해결책)
라즈베리파이-PC 간 이더넷 직결 또는 스위치 연결로 무선 트래픽 경쟁에서 완전히 벗어남.

### 4. (참고, 미적용) DDS 트래픽 최소화
```bash
echo $RMW_IMPLEMENTATION
```
필요 시 `rmw_cyclonedds_cpp` 등으로 교체하거나 QoS(`BEST_EFFORT` vs `RELIABLE`) 조정을 검토할 수 있음(테스트 필요, 이번 세션에서 실제 적용은 하지 않음).

---

## 9. 최종 정리 — 이번 세션에서 해결/확인된 항목

| 문제 | 상태 |
|---|---|
| `use_sim_time: True`로 잘못 설정 | ✅ 수정 완료 (전체 False로 변경, 새 params_file 적용) |
| 시스템 파일 권한 문제로 sed 실패 | ✅ 사용자 경로(`~/nav2_config/`)로 복사하여 해결 |
| 노드 중복 실행 (robot_state_publisher 등) | ✅ pkill로 정리, 현재 각 1개씩 정상 |
| `global_costmap` activating에서 멈춤 | ✅ 원인 규명: `map` 프레임 부재 |
| AMCL 초기 위치 미설정 → map 프레임 미발행 | ✅ `2D Pose Estimate`로 해결, 전체 노드 active 확인 |
| `/scan` 메시지 지연/드롭 (최대 2초) | ⚠️ 원인 규명(네트워크 공유 환경), **조치는 아직 미적용** — 다음 단계 필요 |
| RViz Docking/Selector 패널 로드 에러 | ℹ️ 별도 이슈, 기능상 영향 없음, 미해결 상태로 남음 |

## 10. 다음 단계 (향후 진행 필요)

1. `ROS_DOMAIN_ID`를 팀 간 겹치지 않는 값으로 변경 (PC + 라즈베리파이 동일하게)
2. 변경 후 `ros2 topic hz /scan`, `ros2 topic delay /scan` 재측정하여 지연 개선 여부 확인
3. AMCL 파티클 수렴 여부 및 실제 주행 시 망설임 현상 재관찰
4. 가능하다면 유선 연결로 전환하여 근본적으로 무선 경쟁 요인 제거
