# WiFi 5G→2G 전환 + 핫스팟(멀티캐스트 vs 유니캐스트) 진단 기록 (2026-08-28)

터틀봇 리더 PC(`ros1@victus`)와 팔로워 Pi(`raspberrypi`) 사이 ROS 2 통신이 안 되던
문제를 끝까지 추적한 기록. 공유기 교체 이후 겪은 문제들의 후속편이며,
최종적으로 **"멀티캐스트가 이 WiFi 환경에서 근본적으로 신뢰할 수 없다"**는
결론에 도달해 ROS 2 디스커버리 방식 자체를 바꾸는 것으로 해결했다.

---

## 1. 5GHz → 2.4GHz 전환 (신호 세기 문제)

리더 PC(`victus`)가 공유기의 5GHz SSID에 붙어 있었는데 `signal: -76 dBm`으로
약했다. 손실률은 0%였지만 지연시간이 `2ms ~ 117ms` 사이를 계속 크게 오갔다
(`mdev`가 매우 큼 — "안 끊기지만 매번 들쭉날쭉한" 전형적 패턴).

같은 이름(`Kisuk_WIFI`)으로 2.4GHz 대역도 같이 방송되고 있어서, 그쪽 BSSID로
강제 이동:

```bash
nmcli dev wifi list                              # FREQ 컬럼: 24xx=2.4GHz, 5xxx=5GHz
nmcli connection delete "Kisuk_WIFI"             # 기존 저장된 프로필 삭제 (안 지우면 재사용되며 무시됨)
nmcli connection add type wifi ifname wlo1 con-name Kisuk_2G ssid "Kisuk_WIFI" \
  wifi.bssid <원하는 2.4GHz AP의 BSSID> \
  wifi-sec.key-mgmt wpa-psk wifi-sec.psk '<비밀번호>'   # 특수문자(!) 있으면 반드시 작은따옴표
nmcli dev wifi rescan && sleep 3 && nmcli connection up Kisuk_2G   # 재스캔 후 바로 접속해야 "찾을 수 없음" 오류 회피
```

결과: `-65dBm`으로 개선, 지연 변동폭(`mdev`)도 크게 줄었다(단, 2.4GHz는 채널이
1/6/11 셋뿐이라 이 건물에 공유기가 몰려있어 완전히 0은 아니었음).

Pi(`wlan0`)는 netplan에 `band: 2.4GHz`를 이미 지정해둔 상태였고, 확인 결과
Pi와 PC 둘 다 **완전히 같은 BSSID**(`38:17:c3:19:0d:e0`), 같은 주파수
(`2412MHz`)에 붙어 있는 것으로 확인됨 — 이 부분은 추가 조치 불필요, 완료 상태.

---

## 2. `/cmd_vel`이 로봇에 안 닿는 문제 → 멀티캐스트 완전 차단 발견

teleop_keyboard로 로봇이 안 움직이는 문제를 추적하는 과정에서 발견한 문제 사슬:

1. **`ROS_DOMAIN_ID` 불일치** (Pi의 새 SSH 세션이 `11`이 아닌 값이었음, 과거에도
   한 번 겪은 패턴) → `export ROS_DOMAIN_ID=11`로 양쪽 맞춤. 하지만 이것만으로는
   해결 안 됨.
2. 맞춘 뒤에도 `ros2 topic info /cmd_vel --verbose`에서 Pi 쪽엔
   **`Publisher count: 0`** — PC의 teleop이 보낸 발행을 Pi가 계속 못 봄.
3. `ros2 multicast send`(PC) / `ros2 multicast receive`(Pi)로 직접 테스트 →
   **Pi가 단 한 번도 수신 못 함.** `ping`은 완벽하게 잘 되는데(유니캐스트 정상)
   ROS 2 디스커버리가 쓰는 멀티캐스트만 전혀 전달 안 되는 상황.

처음엔 "여러 AP가 로밍하는 회사/캠퍼스 WiFi(`Kisuk_WIFI`, AP 9개 이상)가 클라이언트
간 멀티캐스트를 정책으로 막고 있다"고 의심함.

---

## 3. 검증을 위한 사설 핫스팟 시도 — 그래도 멀티캐스트만 안 됨

이 가설을 확인하려고, 노트북의 USB WiFi 동글(`wlxfc221c204d1a`)로 완전히
독립된 사설 네트워크를 만들어 재현 시도. (내장 `wlo1`은 그대로 `Kisuk_WIFI`에
남겨둬서 PC 인터넷은 유지.)

```bash
# PC: 동글로 핫스팟 생성
nmcli device status                       # 동글 인터페이스 이름 확인 (wlx로 시작)
nmcli dev wifi hotspot ifname wlxfc221c204d1a ssid TB3_TEST password '12345678'
```

Pi는 NetworkManager가 없어(netplan/networkd 방식) 파일을 직접 수정. **원래
설정은 반드시 백업 후 진행**:

```bash
sudo cp /etc/netplan/50-cloud-init.yaml /etc/netplan/50-cloud-init.yaml.kisuk-backup

sudo tee /etc/netplan/50-cloud-init.yaml > /dev/null << 'EOF'
network:
    version: 2
    wifis:
        renderer: networkd
        wlan0:
            access-points:
                TB3_TEST:
                    password: "12345678"
            dhcp4: true
            nameservers:
                addresses: [8.8.8.8, 1.1.1.1]
            optional: true
EOF
sudo netplan apply   # 이 순간 기존 SSH 세션은 끊긴다 (정상, 새 IP로 재접속하면 됨)
```

새 IP는 PC에서 핫스팟 대역을 스캔해서 찾음 (`10.42.0.0/24`가 NetworkManager
핫스팟 기본 대역):
```bash
nmap -sn 10.42.0.0/24
ssh pi@<새로_잡힌_IP>
```

**결과 — 유니캐스트(ping)는 완벽, 멀티캐스트는 이 사설망에서도 여전히 실패:**
```
ping 10.42.0.1  (Pi→PC)   : 0% loss, ~1-2ms
ping 10.42.0.235 (PC→Pi)  : 0% loss, ~1-2ms
ros2 multicast send/receive : Pi는 계속 "Waiting..." 상태, 한 번도 수신 못 함
```

**결론**: 이 사설 네트워크엔 어떤 정책도 없으므로, "캠퍼스 WiFi가 멀티캐스트를
막는다"는 가설은 기각. 근본 원인은 그보다 낮은 레벨 — 유력한 후보는
**USB WiFi 동글의 소프트웨어 AP(hostapd) 모드가 자신에게 붙은 클라이언트끼리의
멀티캐스트 프레임을 제대로 중계하지 못하는 드라이버/하드웨어 한계**로 추정.
다만 100% 확정된 원인은 아니며, 실용적으로는 "이 환경에서 멀티캐스트는
믿을 수 없다"는 사실만 확정하고 다음 단계(§4)로 넘어감.

핫스팟 테스트가 끝난 뒤 Pi는 원래 설정으로 복구:
```bash
sudo cp /etc/netplan/50-cloud-init.yaml.kisuk-backup /etc/netplan/50-cloud-init.yaml
sudo netplan apply   # 다시 172.16.7.50 (Kisuk_WIFI)로 접속
```

---

## 4. 최종 해결 — Fast DDS Discovery Server (멀티캐스트 완전 우회)

ROS 2 기본 디스커버리(SPDP)는 멀티캐스트로 "누구 있냐"를 방송하는 방식이라
지금 환경에선 원천적으로 불리하다. 대신 **Discovery Server**를 쓰면 정해진
한 대(PC)가 "동사무소" 역할을 하고, 나머지는 전부 그 주소로 유니캐스트로만
등록한다 — 유니캐스트는 이미 확인했듯 완벽하게 되므로 이 환경에 딱 맞음.

```bash
# PC: 서버 실행 (전용 터미널 하나에 계속 띄워둠)
fastdds discovery --server-id 0 -p 11811

# PC, Pi 양쪽 — ROS 2 프로세스를 띄우는 모든 터미널에서, 실행 "전에" export
export ROS_DISCOVERY_SERVER="172.16.6.169:11811"   # PC의 현재 Kisuk_WIFI IP
```

**주의할 점**
- `ROS_DISCOVERY_SERVER`는 프로세스가 **시작되기 전에** 걸려 있어야 적용된다.
  이미 떠 있는 프로세스는 재시작해야 함.
- 새 터미널을 열 때마다 다시 export해야 하므로, 매번 반복하기 싫으면
  `~/.bashrc`에 추가해두는 게 편함:
  ```bash
  echo 'export ROS_DISCOVERY_SERVER="172.16.6.169:11811"' >> ~/.bashrc
  ```
- **PC의 IP(`172.16.6.169`)는 DHCP로 받은 동적 주소** — 공유기 재시작이나
  PC 재부팅으로 바뀔 수 있음. 바뀌면 이 값 전체를 다시 맞춰야 하므로,
  가능하면 PC도 고정 IP로 박아두는 게 장기적으로 안전함 (아직 미적용).

**검증**: teleop_keyboard로 실제 로봇이 움직이는 것까지 확인 완료.

---

## 5. 다음에 이 문제를 또 만나면 (요약 체크리스트)

1. `echo $ROS_DOMAIN_ID` 양쪽 확인 — 다르면 여기서 끝. (가장 흔한 원인, 매번 제일 먼저 확인)
2. `ping`은 되는데 `ros2 topic info <토픽> --verbose`에서 상대 쪽 Publisher/Subscriber
   count가 0이면 → 멀티캐스트 의심.
3. `ros2 multicast send`(한쪽) / `ros2 multicast receive`(다른 쪽)로 직접 확인.
   **반드시 `receive`를 먼저 켜서 대기시킨 상태에서 `send`를 실행** (순서/터미널 헷갈리지 말 것).
4. 안 되면 네트워크를 바꿔가며 재현할 필요 없이(이미 사설망에서도 안 됐던 전례가 있음),
   바로 §4의 Discovery Server로 우회하는 게 시간 절약됨.
