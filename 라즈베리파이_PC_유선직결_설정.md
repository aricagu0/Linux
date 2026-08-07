# 라즈베리파이4 ↔ PC 유선 직결 설정 (ROS2 rqt_image_view 속도 개선)

## 배경
- 교실에서 같은 공유기를 여러 명이 공유하며 ROS2 이미지 토픽(`rqt_image_view`)이 매우 느리게 동작 (10Hz로 낮춰도 느림)
- 원인: Wi-Fi/공유기 대역폭 혼잡
- 해결 방향: PC와 라즈베리파이4를 랜케이블로 1:1 직결하여 공유기를 거치지 않는 전용 통신 채널 구성

## 최종 구성
```
PC (유선 랜포트, 공유기에서 케이블 분리) ↔ 랜케이블 직결 ↔ 라즈베리파이4 (eth0)
```
- DHCP 서버가 없는 순수 1:1 직결이므로 양쪽 모두 **수동(Manual) 고정 IP** 사용
- 같은 서브넷 안에 기기가 둘뿐이고 외부로 나갈 트래픽이 없으므로 **게이트웨이는 비워둠**

| 장치 | IP | Netmask | Gateway |
|---|---|---|---|
| PC (Wired) | 192.168.100.1 | 255.255.255.0 | (없음) |
| 라즈베리파이4 (eth0) | 192.168.100.2 | 255.255.255.0 | (없음) |

## 라즈베리파이4 설정 (Ubuntu 22.04, netplan 사용)

Ubuntu 22.04에는 `nmcli`/`dhcpcd`가 없고 **netplan(systemd-networkd)** 방식 사용.

```bash
# 인터페이스 이름 확인 (eth0 / end0 등)
ip a

# netplan 설정 파일 확인
ls /etc/netplan/
cat /etc/netplan/*.yaml

# 설정 파일 수정
sudo nano /etc/netplan/50-cloud-init.yaml
```

```yaml
network:
  version: 2
  ethernets:
    eth0:
      dhcp4: no
      addresses:
        - 192.168.100.2/24
```

```bash
# 적용
sudo netplan apply

# 확인
ip a show eth0
```

## PC 설정 (GNOME Network Settings)

Wired → 톱니바퀴 → **IPv4** 탭
- Method: **Manual**
- Address: `192.168.100.1`
- Netmask: `255.255.255.0`
- Gateway: **비워둠**
- **Apply** 클릭

## 트러블슈팅 과정

### 1) `nmcli` 명령어 없음
- Ubuntu 22.04는 NetworkManager 대신 netplan 사용 → 위 netplan 방식으로 해결

### 2) ping 100% 패킷 손실
`ip a` 확인 결과:
```
2: eno1: <NO-CARRIER,BROADCAST,MULTICAST,UP> ... state DOWN
```
- **원인 1**: `eno1`에 IP 주소가 아예 안 잡혀 있었음 (GNOME에서 Apply한 설정이 실제 인터페이스에 반영 안 됨)
- **원인 2 (진짜 원인)**: `NO-CARRIER` — 케이블 링크 자체가 물리적으로 인식 안 되는 상태 (케이블 미접촉/오삽입)
- **해결**: 케이블 재점검 및 재연결 → 정상 링크(`LOWER_UP`) 확인 후 해결됨

## 확인 명령어 모음

```bash
# 링크 상태 및 IP 확인
ip a
ip link show

# 라우팅 테이블 확인
ip route

# 연결 테스트
ping 192.168.100.2   # PC에서
ping 192.168.100.1   # 라즈베리파이에서

# ROS2 통신 확인
ros2 topic list
ros2 topic hz /image_raw

# 라즈베리파이 Wi-Fi 끄기 (DDS 혼선 방지, 필요시)
sudo ip link set wlan0 down
```

## 참고: 추가 대역폭 절감 옵션
`image_transport`의 `compressed` 플러그인을 사용하면 raw 이미지 대신 JPEG 압축 스트림으로 구독 가능 (`rqt_image_view`에서 토픽 뒤에 `/compressed` 붙여서 구독). 유선 직결이 여의치 않을 때 보조 수단으로 활용 가능.
