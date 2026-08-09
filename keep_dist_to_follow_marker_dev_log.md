# 터틀봇 팔로워 - keep_dist.py 분석 및 follow_marker.py 개발 기록

---

## 1. keep_dist.py 구조적 한계 분석

거리 유지(20cm 근처 정지)는 성공한 상태에서, 조향(steering)까지 추가하기 전에
기존 `keep_dist.py` 코드의 구조적 한계를 먼저 짚었다.

### ① 각속도(angular.z) 제어가 아예 없음 — 가장 중요한 문제

기존 코드는 `tw.linear.x`만 계산하고 `tw.angular.z`는 한 번도 설정하지 않는다.
즉 거리 유지만 되고 좌우로 방향을 트는 기능이 없다. 리더가 코너를 돌면 팔로워는
그냥 직진/후진만 하다가 마커를 놓친다. "따라가기" 코드의 핵심은 이 조향 로직이다.

### ② `target_found` 판정 로직에 버그가 있음

```python
for i in range(len(msg.marker_ids)):
    if msg.marker_ids[i] == TARGET_ID:
        self.target_found = True
        ...
    else:
        self.target_found = False   # ← 문제
```

마커가 여러 개 인식될 때, target이 아닌 다른 마커의 인덱스를 처리하는 순간
`target_found`가 다시 `False`로 덮어써진다. 예를 들어 `marker_ids = [3, 5]`이고
target이 3번이면, i=0에서 True가 됐다가 i=1에서 5번을 만나 다시 False가 되어버린다.
마커가 하나만 있을 때는 안 드러나지만, 리더+팔로워 마커가 동시에 카메라에 잡힐
경우를 대비해 반드시 고쳐야 한다.

### ③ 마커를 놓쳤을 때 안전 정지가 없음

`target_found`가 `False`가 돼도 `tw.linear.x`는 직전 값을 그대로 유지한 채
계속 publish된다. 마커를 놓친 순간 로봇이 마지막 속도로 계속 달리는 셈이라 위험하다.
반드시 `target_found == False`일 때는 `tw.linear.x = 0`, `tw.angular.z = 0`으로
강제해야 한다.

### ④ 토픽 자체가 끊기는 경우는 감지 못함

카메라 노드가 죽거나 `aruco_markers` 토픽 발행이 멈추면 콜백 자체가 안 불려서
`dist`, `theta`가 예전 값에 멈춘 채 계속 사용된다. `target_found`만으로는 이걸
못 잡는다. 마지막 메시지 수신 시각을 기록해두고, 일정 시간(예: 0.5초) 이상
메시지가 없으면 강제 정지시키는 워치독(watchdog)이 필요하다.

### ⑤ Bang-bang 제어라 진동 가능성

`DIST_REF ± 0.05` 데드밴드 밖이면 무조건 고정속도(`LINSPD`)로 전/후진하는 구조.
정지된 마커 추종엔 괜찮지만, 리더가 계속 움직이는 상황에서는 팔로워가 앞서거니
뒤서거니 하며 덜컹거릴 수 있다. 거리 오차에 비례하는 속도(P제어)로 바꾸면
훨씬 부드럽다.

---

## 2. 조향(각도) 로직 추가 시 고려할 점

기존 코드의 `theta`는 마커 자체의 자세(pitch)에서 나온 값이라 "팔로워가 마커를
향해 얼마나 틀어야 하는지"와는 다른 값이다. 조향에는 마커의 좌우 위치
(`pose.position.x`, `pose.position.z`)로 계산한 **방위각(bearing angle)**을
쓰는 게 더 직관적이다.

```python
from math import atan2
angle_to_marker = atan2(self.pose.position.x, self.pose.position.z)
```

이 값이 0이면 정면, +면 오른쪽으로 치우침, -면 왼쪽으로 치우침 — 이런 식으로
`angular.z = -Kp_ang * angle_to_marker` 로 조향한다. (부호는 좌표계 실제 테스트하며
맞춰야 함)

---

## 3. 선두 로봇(리더) 저속 주행 — 왜 중요하고 어떻게

리더가 저속으로 가야 하는 이유:
- 팔로워의 마커 인식 루프가 카메라 프레임레이트 + 인식 처리 시간에 묶여있어서,
  리더가 빠르면 팔로워 반응이 따라가지 못하고 마커를 놓친다.
- 특히 회전 시는 마커가 카메라 FOV 밖으로 순식간에 빠져나가므로 선속도보다
  각속도 제한이 더 중요하다.

Nav2에서 저속으로 제한하는 방법:
- `nav2_params.yaml`의 controller_server 설정에서 `max_vel_x`, `max_vel_theta`를 낮게 설정
- 가속도 제한(`acc_lim_x`, `acc_lim_theta`)도 같이 낮춰야 급가속/급회전이 안 생김
- 처음 테스트는 직선 구간 위주로, 회전 구간은 별도로 각속도 값을 더 보수적으로 잡고 테스트

---

## 4. 마커/카메라 관련 사전 점검

- 4.2cm 마커면 인식 가능한 최대 거리가 상당히 짧을 가능성이 높음. `DIST_REF=0.2m`은
  여유가 있지만, 리더가 움직이면서 팔로워와의 거리가 순간적으로 벌어질 때 인식이
  끊기지 않는지 먼저 정적 상태에서 최대 인식거리를 실측 필요
- 카메라 노출/셔터스피드 — 로봇이 움직이면서 생기는 모션 블러로 인식률이 떨어질 수 있음
  (정지 상태 테스트와 이동 중 테스트는 결과가 다를 수 있음)

---

## 5. 통합 전 테스트 순서

1. `keep_dist.py`에 조향 로직 + 안전정지(타겟 미검출/토픽 끊김) + target_found 버그 수정부터 반영
2. 팔로워 정지 상태에서 마커(3번)를 손으로 좌우로 흔들며 조향이 잘 따라오는지 확인 (리더 없이)
3. 리더 저속 직진만 시키고 팔로워가 잘 따라오는지 확인
4. 리더 저속 회전 포함시켜서 팔로워가 마커를 놓치지 않는지, 놓쳤을 때 안전정지가 잘 되는지 확인
5. 마지막에 Nav2 좌표 이동 + 팔로워 실시간 추종 통합

---

## 6. cam.sh 프레임레이트 확인 — 설정값과 실제값의 불일치

`cam.sh`의 `v4l2-ctl -d /dev/video0 --set-parm=5`는 5fps를 요청하는 설정이었으나,
USB 카메라 하드웨어 자체의 최저 지원 fps가 15로 정해져 있어 실제로는 **15fps로
클램핑(clamping)**되어 동작할 가능성이 높다는 점을 확인했다.

확인 명령:
```bash
v4l2-ctl -d /dev/video0 --get-parm
ros2 topic hz /aruco_markers
```

15Hz 기준 재계산:
```
프레임 주기 = 1 / 15Hz ≈ 0.067초
여유 거리 5cm 기준 리더 최대 속도 ≈ 0.05m / 0.067s ≈ 0.75 m/s
```

---

## 7. 정적 상태 최대 인식거리 실측 방법

### 준비물
- 줄자 또는 바닥에 10cm 간격 표시(테이프)
- 3번 마커(4.2cm), 조명은 실제 운용할 환경과 동일하게
- 팔로워 로봇(카메라)은 고정, 마커도 고정된 상태에서 거리만 변경

### 절차
1. `ros2 topic echo /aruco_markers`로 인식 토픽을 실시간 모니터링
2. 거리를 10cm 단위로 벌려가며 인식 성공/실패 기록 (각 거리에서 최소 10초 이상
   정지 상태로 두고 marker_ids가 끊김 없이 계속 채워지는지 확인)

| 거리(cm) | 인식 여부 | 비고 |
|---|---|---|
| 20 | O | 안정적 |
| 40 | O | 안정적 |
| 60 | △ | 간헐적 끊김 |
| 80 | X | 미인식 |

3. 각도(카메라 정면 대비 좌우 편차)까지 최대 인식거리의 70~80% 지점에서 테스트
4. 이동 중(모션 블러 포함) 상황에서도 반복 — 정적 결과 대비 60~70% 수준을
   실제 운용 target_distance 상한으로 잡을 것
5. `ros2 topic hz /aruco_markers`로 인식 주기(Hz) 실측

**실측 결과: 정적 최대 안정 인식거리 90cm, 실효 주기 10Hz**

---

## 8. follow_marker.py 파라미터 설계 근거 (실측값 90cm, 10Hz 반영)

```
프레임 주기 = 1/10Hz = 0.1초
정적 최대 안정 인식거리 = 0.90m
```

- 이동 중에는 모션 블러 때문에 정적 실측치보다 짧아지므로, 운용 범위는 최대거리의
  60~70%로 설정 → 0.55~0.60m를 "이 안에서만 안정적으로 인식된다"는 상한으로 설정
- 목표 추종거리(`TARGET_DIST`)는 이 상한의 절반 정도인 0.35m로 설정 → 리더가
  갑자기 멀어져도 인식 상한(0.6m)까지 여유가 남아있음
- 최소 정지거리(`STOP_DIST`)는 충돌 방지용으로 0.15m
- 통신/처리 지연으로 인한 "마커 놓침"은 0.1초(1프레임) 이상 결과가 안 갱신되면
  감지하도록 워치독을 걸고, 안전하게 0.3초(3프레임) 이상 미인식 시 완전 정지

### 코드 핵심 설명

**1. keep_dist.py의 3가지 문제를 모두 수정**
- 조향 추가: `atan2(pose.position.x, pose.position.z)`로 마커의 좌우 방위각을
  계산해 `angular.z`를 제어 (기존 코드는 `linear.x`만 있었음)
- `target_found` 버그 수정: for문 안에서 즉시 덮어쓰지 않고, `found` 플래그로
  찾은 즉시 `break` 후 루프 밖에서 한 번만 반영
- 안전 정지 추가: `target_found=False`거나 워치독 타임아웃(0.3초 = 3프레임) 초과
  시 무조건 `linear.x=0, angular.z=0`

**2. 실측값(90cm, 10Hz) 반영 지점**
- `STATIC_MAX_DIST = 0.90` → `TRACK_MAX_DIST = 0.60` (약 65% 마진, 이동 중 모션블러 대비)
- `TARGET_DIST = 0.35` (운용 상한의 절반 수준으로, 리더가 순간적으로 멀어져도 여유 확보)
- `WATCHDOG_TIMEOUT = 3 × (1/10Hz) = 0.3초` — 10Hz 기준 3프레임 연속 미검출 시 정지

**3. Bang-bang → P제어로 변경**
거리 오차(`dist_error`)에 비례해서 속도를 계산하도록 바꿔서, 리더가 계속 움직이는
상황에서도 덜컹거리지 않고 부드럽게 추종하도록 했다.

### follow_marker.py (초기 버전)

```python
#!/usr/bin/env python3
"""
follow_marker.py
-----------------
선두 로봇 후면에 부착된 AR(ArUco) 마커를 인식하여
 1) 목표 거리 유지 (P제어, 거리에 비례한 속도)
 2) 좌우 편차에 따른 조향 (P제어, atan2 기반 방위각)
 3) 마커 미검출/토픽 끊김에 대한 안전 정지(watchdog)
를 수행하는 팔로워 노드.

실측 기반 파라미터:
- 카메라 실효 인식 주기        : 10 Hz  (측정값, cam.sh + ros2 topic hz 로 확인)
- 정적 상태 최대 안정 인식거리  : 0.90 m (측정값)
- 이동 중에는 모션 블러 등으로 실측치보다 짧아지므로
  안전 마진을 두어 "운용 상한거리(TRACK_MAX_DIST)"를 0.60m로 설정
  (최대 인식거리의 약 65% 수준)

사용법:
    python3 follow_marker.py <target_marker_id>
    예) python3 follow_marker.py 3
"""

import sys
import time
from math import atan2

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile

from geometry_msgs.msg import Pose, Twist
from ros2_aruco_interfaces.msg import ArucoMarkers


# ------------------------------------------------------------------
# 실측 기반 파라미터
# ------------------------------------------------------------------
CAM_HZ = 10.0                 # 실측 카메라(aruco_markers 토픽) 발행 주기
FRAME_PERIOD = 1.0 / CAM_HZ   # 0.1 s

STATIC_MAX_DIST = 0.90        # 정적 상태 최대 안정 인식거리 (실측값)
TRACK_MAX_DIST = 0.60         # 이동 중 안전 마진 반영 운용 상한거리 (약 65%)

TARGET_DIST = 0.35            # 목표 추종 거리 (TRACK_MAX_DIST의 절반 수준)
DIST_DEADBAND = 0.03          # 목표거리 ±3cm 이내는 정지(떨림 방지)

STOP_DIST = 0.15              # 이 거리보다 가까우면 무조건 후진/정지 (충돌 방지)

MAX_LIN_SPD = 0.15            # 팔로워 최대 선속도 (리더보다 낮거나 비슷하게, 저속 권장)
MAX_ANG_SPD = 0.8             # 팔로워 최대 각속도 (rad/s)

KP_LIN = 0.6                  # 거리오차 -> 선속도 비례 게인
KP_ANG = 1.5                  # 방위각오차 -> 각속도 비례 게인

# 워치독: 최근 몇 프레임 이상 마커가 안 보이면 정지시킬지
LOST_STOP_FRAMES = 3          # 3프레임(0.3s) 이상 미검출 -> 정지
WATCHDOG_TIMEOUT = LOST_STOP_FRAMES * FRAME_PERIOD

CONTROL_HZ = 20.0             # 제어 루프 주기 (카메라 주기보다 빠르게 돌려도 무방,
                               # 실제 새 데이터는 CAM_HZ 주기로만 갱신됨)


class FollowMarker(Node):
    def __init__(self, target_id: int):
        super().__init__('follow_marker')
        qos_profile = QoSProfile(depth=10)

        self.target_id = target_id

        self.sub_ar_pose = self.create_subscription(
            ArucoMarkers,
            'aruco_markers',
            self.marker_callback,
            qos_profile)

        self.pub_cmd_vel = self.create_publisher(Twist, '/cmd_vel', 10)

        self.pose = Pose()
        self.dist = 0.0
        self.angle_to_marker = 0.0

        self.target_found = False          # 이번 메시지에서 target_id를 찾았는지
        self.last_seen_time = time.time()  # 마지막으로 target_id를 본 시각 (watchdog용)

        self.timer = self.create_timer(1.0 / CONTROL_HZ, self.control_loop)

        self.get_logger().info(
            f'follow_marker started. target_id={self.target_id}, '
            f'TARGET_DIST={TARGET_DIST}m, TRACK_MAX_DIST={TRACK_MAX_DIST}m'
        )

    # ------------------------------------------------------------------
    # 마커 인식 콜백
    # ------------------------------------------------------------------
    def marker_callback(self, msg: ArucoMarkers):
        found = False

        # [버그 수정 지점]
        # 기존 코드는 for문 안에서 target이 아닌 마커를 만나면
        # target_found를 다시 False로 덮어써서, 여러 마커가 동시에
        # 인식될 때 오작동하는 문제가 있었음.
        # -> found 플래그로 한 번 찾으면 즉시 break, 루프 종료 후에만
        #    self.target_found를 갱신하도록 수정.
        for i in range(len(msg.marker_ids)):
            if msg.marker_ids[i] == self.target_id:
                self.pose = msg.poses[i]
                self.dist = self.pose.position.z
                self.angle_to_marker = atan2(
                    self.pose.position.x, self.pose.position.z)
                found = True
                self.last_seen_time = time.time()
                break

        self.target_found = found

    # ------------------------------------------------------------------
    # 제어 루프 (watchdog 포함)
    # ------------------------------------------------------------------
    def control_loop(self):
        tw = Twist()

        elapsed_since_seen = time.time() - self.last_seen_time

        # [안전 정지 조건 1] 이번 콜백에서 target을 못 찾음
        # [안전 정지 조건 2] watchdog: 마지막으로 본 지 WATCHDOG_TIMEOUT 이상 경과
        #                    (토픽 자체가 끊긴 경우까지 포함해서 감지)
        if (not self.target_found) or (elapsed_since_seen > WATCHDOG_TIMEOUT):
            tw.linear.x = 0.0
            tw.angular.z = 0.0
            self.pub_cmd_vel.publish(tw)

            if elapsed_since_seen > WATCHDOG_TIMEOUT:
                self.get_logger().warn(
                    f'Marker lost for {elapsed_since_seen:.2f}s -> STOP',
                    throttle_duration_sec=1.0
                )
            return

        # [운용 상한거리 초과] 인식은 됐지만 안정 인식 범위를 벗어난 경우
        # -> 무리하게 따라잡으려 하지 않고 최대속도로만 접근 (급가속 방지)
        dist = self.dist
        if dist > TRACK_MAX_DIST:
            self.get_logger().warn(
                f'dist={dist:.2f}m exceeds TRACK_MAX_DIST={TRACK_MAX_DIST}m',
                throttle_duration_sec=1.0
            )

        # ------------------------------------------------------------
        # 거리 제어 (P제어, deadband 포함)
        # ------------------------------------------------------------
        dist_error = dist - TARGET_DIST

        if dist < STOP_DIST:
            # 너무 가까움 -> 후진
            lin_spd = -MAX_LIN_SPD * 0.5
        elif abs(dist_error) < DIST_DEADBAND:
            lin_spd = 0.0
        else:
            lin_spd = KP_LIN * dist_error
            lin_spd = max(min(lin_spd, MAX_LIN_SPD), -MAX_LIN_SPD)

        # ------------------------------------------------------------
        # 조향 제어 (P제어, 방위각 기반)
        # angle_to_marker > 0 : 마커가 오른쪽에 있음 -> 오른쪽으로 회전 필요
        # angle_to_marker < 0 : 마커가 왼쪽에 있음   -> 왼쪽으로 회전 필요
        # (부호는 실제 좌표계 확인 후 반대일 경우 -1 곱해서 뒤집을 것)
        # ------------------------------------------------------------
        ang_spd = -KP_ANG * self.angle_to_marker
        ang_spd = max(min(ang_spd, MAX_ANG_SPD), -MAX_ANG_SPD)

        tw.linear.x = lin_spd
        tw.angular.z = ang_spd
        self.pub_cmd_vel.publish(tw)


def main(args=None):
    if len(sys.argv) < 2:
        print('Usage: python3 follow_marker.py <target_marker_id>')
        sys.exit(1)

    target_id = int(sys.argv[1])

    rclpy.init(args=args)
    node = FollowMarker(target_id)

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info('Keyboard Interrupt(SIGINT)')
    finally:
        # 종료 시 반드시 정지 명령을 한 번 보내고 종료
        stop_tw = Twist()
        node.pub_cmd_vel.publish(stop_tw)
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
```

### 실행 전 확인 사항
1. `ang_spd`의 부호 — `angle_to_marker`의 좌우 부호가 실제 카메라 좌표계와 맞는지
   확인 필요. 처음 테스트할 때는 팔로워를 들어서 바퀴가 땅에 안 닿게 한 상태로
   마커를 좌우로 흔들며 바퀴 회전 방향이 맞는지부터 확인 권장. 반대로 돌면
   `KP_ANG` 부호만 뒤집으면 됨.
2. `MAX_LIN_SPD=0.15` — 리더 속도보다 같거나 살짝 높게 잡았는데, 실제 리더 Nav2
   속도를 확정하면 그에 맞춰 조정
3. 테스트는 순서(①정지 상태 조향 확인 → ②리더 저속 직진 추종 → ③리더 저속 회전
   포함)대로 단계적으로 진행

---

## 9. 첫 실행 결과 — Marker Lost 반복 및 종료 크래시

```
os@ros1:~/robot_ws$ ros2 run ar_marker follow_maker 3
[INFO] [1786174787.481361215] [follow_marker]: follow_marker started. target_id=3, TARGET_DIST=0.35m, TRACK_MAX_DIST=0.6m
[WARN] [1786174788.374539430] [follow_marker]: Marker lost for 0.33s -> STOP
[WARN] [1786174789.424443084] [follow_marker]: Marker lost for 0.52s -> STOP
[WARN] [1786174790.624510704] [follow_marker]: Marker lost for 0.32s -> STOP
[WARN] [1786174791.874462733] [follow_marker]: Marker lost for 0.30s -> STOP
[WARN] [1786174794.624386558] [follow_marker]: Marker lost for 0.31s -> STOP
^C[INFO] [1786174794.728797356] [follow_marker]: Keyboard Interrupt(SIGINT)
Failed to publish log message to rosout: publisher's context is invalid, at ./src/rcl/publisher.c:389
Traceback (most recent call last):
  File "/home/ros/robot_ws/install/ar_marker/lib/ar_marker/follow_maker", line 33, in <module>
    sys.exit(load_entry_point('ar-marker', 'console_scripts', 'follow_maker')())
  File "/home/ros/robot_ws/build/ar_marker/ar_marker/follow_marker.py", line 193, in main
    node.pub_cmd_vel.publish(stop_tw)
  File "/opt/ros/humble/local/lib/python3.10/dist-packages/rclpy/publisher.py", line 70, in publish
    self.__publisher.publish(msg)
rclpy._rclpy_pybind11.RCLError: Failed to publish: publisher's context is invalid, at ./src/rcl/publisher.c:389
[ros2run]: Process exited with failure 1
```

**드러난 두 가지 문제**
1. `Marker lost` 경고가 0.3~0.5초 간격으로 반복 발생 (이후 조사에서 카메라 노드의
   YUYV→RGB8 변환 CPU 부하로 인한 stall이 원인으로 확인됨)
2. `Ctrl+C` 종료 시 `rclpy` context invalid 크래시 (rclpy가 SIGINT 시 먼저
   context를 내려버려서, `finally` 블록의 `publish(stop_tw)`가 이미 죽은 context에
   접근하려다 발생 — 이후 `rclpy.ok()` 체크로 수정됨)
