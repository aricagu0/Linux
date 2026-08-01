# ROS 2 Turtlesim 제어 및 Pose 수신 노드 종합 가이드

ROS 2(Humble) 환경에서 `turtlesim` 거북이를 **키보드로 원격 조종(Publisher)**하는 노드와 **거북이의 현재 각도(theta) 정보를 실시간 수신(Subscriber)**하는 파이썬 노드 가이드 문서입니다.

---

## 📑 목차
1. [키보드 원격 조종 노드 (`remote_turtle.py`)](#1-키보드-원격-조종-노드-remote_turtlepy)
2. [거북이 Pose(각도) 수신 노드 (`turtle_pose.py`)](#2-거북이-pose각도-수신-노드-turtle_posepy)

---

## 1. 키보드 원격 조종 노드 (`remote_turtle.py`)

`Getchar` 비동기 입력을 활용하여 터미널 키보드로 `/turtle1/cmd_vel` 토픽을 발행하는 노드입니다.

### 📌 조작 키
* **`W`**: 전진 (Linear X = +2.0)
* **`S`**: 후진 (Linear X = -2.0)
* **`A`**: 좌회전 (Angular Z = +2.0)
* **`D`**: 우회전 (Angular Z = -2.0)
* **`Space`**: 정지 (Linear X = 0.0, Angular Z = 0.0)
* **`Q`**: 종료

### 💻 소스 코드 (`remote_turtle.py`)
```python
import rclpy
from rclpy.node import Node

from geometry_msgs.msg import Twist
from .getchar import Getchar

class RemoteTurtle(Node):

    def __init__(self):
        super().__init__('remote_turtle')
        self.publisher_ = self.create_publisher(Twist, '/turtle1/cmd_vel', 10)
        timer_period = 2.0  # seconds
        self.timer = self.create_timer(timer_period, self.timer_callback)
        self.i = 0

    def timer_callback(self):
        msg = Twist()
        msg.linear.x = 0.0
        msg.angular.z = 0.0
        self.publisher_.publish(msg)
        self.get_logger().info('Publishing cmd_vel')
        self.i += 1


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = RemoteTurtle()
        kb = Getchar()
        tw = Twist()
        pub = node.create_publisher(Twist, '/turtle1/cmd_vel', 10)
        
        print("\n===== Turtlesim Keyboard Teleop Control =====")
        print("W: Move Forward | S: Move Backward")
        print("A: Rotate Left   | D: Rotate Right")
        print("SPACE: Stop      | Q: Quit")
        print("=============================================\n")

        while rclpy.ok():
            if kb.chk_stdin():
                key = kb.getch()
                if key == 'w':
                    print("move forward")
                    tw.linear.x = 2.0
                    tw.angular.z = 0.0
                elif key == 's':
                    print("move backward")
                    tw.linear.x = -2.0
                    tw.angular.z = 0.0
                elif key == 'a':
                    print("rotate left")
                    tw.linear.x = 0.0
                    tw.angular.z = 2.0
                elif key == 'd':
                    print("rotate right")
                    tw.linear.x = 0.0
                    tw.angular.z = -2.0
                elif key == ' ':
                    print("stop move")
                    tw.linear.x = 0.0
                    tw.angular.z = 0.0
                elif key == 'Q' or key == 'q':
                    print("finish")
                    break
                else:
                    pass
                    
                pub.publish(tw)        
    except KeyboardInterrupt:
        print("\nKeyboard Interrupt detected. Exiting...")
    finally:
        if node is not None:
            node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
```

---

## 2. 거북이 Pose(각도) 수신 노드 (`turtle_pose.py`)

`/turtle1/pose` 토픽을 구독(Subscribe)하여 라디안(Radian) 단위의 회전각(`theta`)을 디그리(Degree, 도) 단위로 변환해 실시간으로 출력하는 노드입니다.

### 💻 소스 코드 (`turtle_pose.py`)
```python
import rclpy
from rclpy.node import Node

from turtlesim.msg import Pose
from math import degrees

class TurtlePose(Node):

    def __init__(self):
        super().__init__('turtle_pose')
        self.create_subscription(
            Pose,
            '/turtle1/pose',
            self.listener_callback,
            10)
        

    def listener_callback(self, msg):
        # 라디안(rad) 단위를 degree(도) 단위로 변환하여 출력
        self.get_logger().info('theta= : "%s"' % degrees(msg.theta))


def main(args=None):
    rclpy.init(args=args)

    node = TurtlePose()

    rclpy.spin(node)

    # Destroy the node explicitly
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
```

---

## 🛠️ 전체 시스템 실행 방법

1. **터미널 1: Turtlesim 시뮬레이터 실행**
   ```bash
   ros2 run turtlesim turtlesim_node
   ```

2. **터미널 2: 거북이 회전 각도(Pose) 실시간 모니터링 노드 실행**
   ```bash
   ros2 run <패키지명> turtle_pose
   ```

3. **터미널 3: 키보드 조종 노드 실행**
   ```bash
   ros2 run <패키지명> remote_turtle
   ```
