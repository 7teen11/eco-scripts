# TAM.md — Tổng hợp Kiến trúc & Thiết kế Hệ thống Update FW NIC

> Tài liệu tóm tắt cô đọng toàn bộ phân tích thư mục `nic/` và phương án kiến trúc cuối cùng để tái sử dụng nhanh, tiết kiệm ngữ cảnh/token.

---

## 1. Hệ thống 1 (Framework hiện tại trong `nic/`, trừ `eco34097.sh`)

### Danh sách file
- `fw_update_helper.sh`: Entry point tải và chạy `main.py`.
- `main.py`: Orchestrator (đọc MAC → tải `ins-<mac>` → tải JSON theo `SPN`/`ORDNUM` → lọc `skip_mos`/`is_after_burnin` → tải FW & script → copy log → cập nhật PXE/iPXE → reboot).
- `eco.json`: Cấu hình mẫu (`fw_update` gồm ECO `34438` ConnectX-6 Dx và `34097` ConnectX-7; `global_setting`). *Lưu ý: dòng 6 có dấu phẩy thừa (trailing comma).*
- `Mellanox_FW_Update.sh`: Worker cài `install_mst.sh`, chạy `mst start`, flash tuần tự mọi `/dev/mst/*` bằng `flint`, xuất `mlxfwmanager`, bật UID LED.
- `set_cmd_fw_update.sh` & `set_cburn_2024.sh`: Cập nhật lệnh boot PXE/iPXE trên `172.21.0.1`.
- `fetch_ins.sh`: Lấy MAC từ `summary.log`, tải và `source ins-<mac>`.

### Các địa chỉ quan trọng của Hệ thống 1 (CHỈ DÙNG NHÓM NÀY)
- **Control / PXE Server (`172.21.0.1`)**:
  - `http://172.21.0.1/instructions/ins-<mac>` (file instruction chứa `ORDNUM`, `SPN`, `DIR`, ...)
  - `http://172.21.0.1/cgi-bin/autoipxe.php` (cập nhật boot iPXE)
  - `http://172.21.0.1/cgi-bin/autopxe.php` (cập nhật boot PXE)
- **Script / FW Server (`172.21.57.147`)**:
  - `http://172.21.57.147/script/` (chứa `main.py`, `install_mst.sh`, `Mellanox_FW_Update.sh`, `set_cmd_fw_update.sh`, `set_cburn_2024.sh`, `fetch_ins.sh`)
  - `http://172.21.57.147/script/config/<ORDNUM>.json` & `.../config/oem_json/<SPN>.json`
  - `http://172.21.57.147/script/config/FW/ECO/<ECO>/<fw_name>`
- **Local / Mount / Hardware**:
  - `/root/sysinfo/stage1.json` (`CBIMG`), `/root/sysinfo/stage2.json` (`SYS_DIR` → MAC), `/root/sysinfo/proc-cmdline.log` (`AFTERBURNIN`), `summary.log`
  - `/root/update_process.log` → copy lên `/mnt/<logging_path>/update_process/<mac>`
  - `/dev/tty1` (output màn hình), `/dev/mst/*` (thiết bị Mellanox)
  - `ipmicfg -raw 0x30 0xd` (bật UID LED)

---

## 2. Hệ thống 2 (`eco34097.sh`) & So sánh nhanh

- **Đặc điểm**: Monolithic Bash script riêng cho ECO `34097` (ConnectX-7, PSID `MT_0000000834`). Dùng `cburnserver` và `172.21.100.1/RC/package/` *(bỏ qua các địa chỉ này ở thiết kế mới)*.
- **Điểm mạnh của Hệ thống 1**: Tự động hóa dây chuyền hoàn toàn (PXE/iPXE, log tập trung, auto-reboot), hỗ trợ chạy nhiều ECO.
- **Điểm mạnh của Hệ thống 2**: Dễ dùng cho người mới (chỉ cần mã ECO, tên file theo ECO), lọc đúng card theo PSID, flash song song, tín hiệu LED Pass/Fail, backup log.
- **Nhược điểm cần khắc phục**: Hệ thống 1 phải sửa JSON + tìm tên file `.bin` dài và `Mellanox_FW_Update.sh` không lọc loại card; Hệ thống 2 bị lặp code (170 dòng/ECO) và chỉ chạy đơn lẻ + treo `sleep inf`.

---

## 3. Ghi chú kỹ thuật về PSID

- **PSID** là mã cố định theo từng **model / PN / biến thể OEM** của card Mellanox (không sinh ngẫu nhiên theo từng chiếc).
- **Không cần biết trước hay nhập tay PSID**: Mã PSID nằm sẵn trong header của file `.bin`, có thể trích xuất tự động bằng `flint`:
  ```bash
  FW_PSID=$(flint -i "$FW_FILE" q | awk '/PSID:/ {print $NF}')
  ```
  Sau đó so khớp với `CARD_PSID` của từng `/dev/mst/*` để chỉ burn đúng loại NIC, bỏ qua các NIC khác loại.

---

## 4. Kiến trúc đề xuất cuối cùng (Đã chốt yêu cầu)

### Ràng buộc
- **Chỉ dùng địa chỉ & công cụ của Hệ thống 1** (`172.21.57.147`, `172.21.0.1`, `install_mst.sh`, `mst`, `flint`, `mlxfwmanager`, `ipmicfg`, `set_cmd_fw_update.sh`, `set_cburn_2024.sh`).
- **Không cần file JSON**.
- **Mỗi ECO có 1 script riêng** (`eco<ID>.sh`).
- **Chạy được nhiều ECO script** trong 1 lần boot trên máy có nhiều NIC khác nhau.
- **Có 1 script khởi động gắn thẳng vào RC của cburn**.

### Cấu trúc trên server `172.21.57.147/script/`
```text
http://172.21.57.147/script/
├── rc_eco_runner.sh        # Script khởi động gắn vào RC của cburn (thuần Bash)
├── lib_mellanox.sh         # Thư viện lõi (tải FW, tự đọc FW_PSID từ .bin, lọc /dev/mst/*, burn)
├── eco/
│   ├── eco34097.sh         # ~5 dòng: khai báo ECO_ID + FW_NAME + gọi lib_mellanox.sh
│   └── eco34438.sh         # ~5 dòng: khai báo ECO_ID + FW_NAME + gọi lib_mellanox.sh
├── install_mst.sh          # Có sẵn
├── set_cmd_fw_update.sh    # Có sẵn
├── set_cburn_2024.sh       # Có sẵn
├── fetch_ins.sh            # Có sẵn
└── config/FW/ECO/<ECO>/<FW_NAME>
```

### Cách gắn vào RC của cburn (dành cho người mới)
```bash
wget -qO rc_eco_runner.sh http://172.21.57.147/script/rc_eco_runner.sh && bash rc_eco_runner.sh 34438 34097
```
Cờ tùy chọn: `--cburn` | `--no-logging` | `--after-burnin` | `--desc <name>` (mặc định `fw`).

### Mẫu script riêng cho từng ECO (`eco/eco34097.sh`)
```bash
#!/bin/bash
ECO_ID="34097"
FW_NAME="fw-ConnectX7-rel-28_47_2682-MCX755106AS-HEA_Ax-UEFI-14.40.10-FlexBoot-3.8.201.signed.bin"

source ./lib_mellanox.sh
update_mellanox_by_eco "$ECO_ID" "$FW_NAME"
```

### Luồng thực thi chuẩn
1. **`rc_eco_runner.sh` khởi tạo 1 lần duy nhất**: lấy MAC + `ins-<mac>` (`172.21.0.1`) + `CBIMG` (`stage1.json`); tải & chạy `install_mst.sh` + `mst start`; tải `lib_mellanox.sh`.
2. **Chạy danh sách ECO truyền vào**: tải `eco/eco<ID>.sh` → convert CRLF→LF → chạy từng ECO (có thể chạy song song vì mỗi ECO tự khóa thiết bị theo `FW_PSID`).
3. **Quy ước Exit Code của mỗi ECO**:
   - `0` (**PASS**): khớp PSID và burn thành công.
   - `2` (**SKIPPED**): máy không gắn loại card này → không báo lỗi, chạy tiếp ECO khác.
   - `1` (**FAIL**): lỗi tải FW hoặc burn thất bại.
4. **Tổng kết & Hậu xử lý**:
   - Chạy `mlxfwmanager | tee -a /root/update_process.log > /dev/tty1`.
   - Copy log lên `/mnt/<logging_path>/update_process/<mac>`.
   - Nếu có ECO `exit 1`: cảnh báo đỏ lên `/dev/tty1` và **dừng (không reboot)**.
   - Nếu tất cả `0` hoặc `2`: bật UID LED (`ipmicfg -raw 0x30 0xd`) → gọi `set_cmd_fw_update.sh` (hoặc `set_cburn_2024.sh`) → `reboot`.
