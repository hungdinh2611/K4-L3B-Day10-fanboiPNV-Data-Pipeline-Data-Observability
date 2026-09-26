# Danh Sách Thành Viên & Báo Cáo Phân Công Nhóm

- **Tên Nhóm:** `fanboiPNV`
- **Mã Nhóm / Lớp:** `K4-L3B-DAY10`
- **Tên Repository Nộp Bài:** `K4-L3B-Day10-fanboiPNV-Data-Pipeline-Data-Observability` — https://github.com/hungdinh2611/K4-L3B-Day10-fanboiPNV-Data-Pipeline-Data-Observability

---

## # Thành viên

Phân công được đối chiếu với lịch sử commit trên nhánh `main` (`git log`). Email là email commit, trùng với tài khoản GitHub của từng người.

| STT | Họ và tên | MSSV | Email | Vai trò & Phân công công việc | Báo cáo cá nhân |
|---:|---|---|---|---|---|
| 1 | Mai Văn Trung | 2A202602513 | trungmv2004@gmail.com | Trưởng nhóm / Pipeline Integrator (`phase1.py`, `corruption_flow.py`, repair, demo UI) | `report/individual_2A202602513_MaiVanTrung.md` |
| 2 | Đinh Bảo Hưng | 2A202602524 | dinhbaohungminecraft123@gmail.com | RAG & Vector Index / Artifacts (ChromaDB, embeddings, `data/`) | `report/individual_2A202602524_DinhBaoHung.md` |
| 3 | Ngô Văn Giáp | 2A202602644 | ngogiap1004@gmail.com | Data Foundation & Corruption (`crossref.py`, `cleaning.py`, `corruption.py`) | `report/individual_2A202602644_NgoVanGiap.md` |
| 4 | Hoàng Anh Tú | 2A202602643 | ttien0181@gmail.com | Observability & Reporting (`quality.py` GX 1.x, `reporting.py`) | `report/individual_2A202602643_HoangAnhTu.md` |
| 5 | Nguyễn Thành Nam | 2A202602694 | nguyenthanhnam12042004@gmail.com | Evaluation Set (`testset.py`, `data/eval/`) | `report/individual_2A202602694_NguyenThanhNam.md` |

---

## # Cá nhân

### ## MaiVanTrung-2A202602513
- **Vai trò:** Trưởng nhóm & Điều phối Pipeline.
- **Công việc chi tiết đã hoàn thành:**
  - Hoàn thiện `run_phase1_pipeline` trong `src/pipelines/phase1.py`, xâu chuỗi các bước Ingest → Clean → Index ChromaDB → Testset → Evaluate → Quality Gate → `data/reports/phase1_report.md`.
  - Hoàn thiện `run_corruption_flow_pipeline` và `repair_from_raw_snapshot` trong `src/pipelines/corruption_flow.py`: corrupt → evaluate → gate → repair idempotent từ raw records → so sánh 3 trạng thái.
  - Merge và tích hợp module của các thành viên, rồi chạy lại toàn bộ flow để kiểm tra (commit `fdb521f`, `d07cec8`).
  - Xây dựng demo UI `src/demo_ui/` (phong cách Brutalism, `script/run_demo_ui.py`) cho bonus B1, và viết kịch bản thuyết trình `report/presentation_script.md`.
- **Điều học được / Đóng góp chính:**
  - Thiết kế pipeline idempotent: repair phụ thuộc raw snapshot chứ không phụ thuộc trạng thái hỏng, và collection được tạo lại mỗi lần index.
  - Chỉ nhìn metric của AI thì không đủ để phát hiện dữ liệu hỏng (silent failure), nên cần có gate ở tầng dữ liệu.

### ## DinhBaoHung-2A202602524
- **Vai trò:** Phụ trách RAG, Vector Database & Artifacts.
- **Công việc chi tiết đã hoàn thành:**
  - Chạy pipeline để sinh và quản lý 3 collection ChromaDB riêng biệt (`papers-baseline`, `papers-corrupted`, `papers-repaired`) với embedding `sentence-transformers/all-MiniLM-L6-v2`.
  - Commit bộ artifact làm bằng chứng: `data/chroma/`, `data/embeddings/`, `data/eval/`, `data/quality/`, `data/results/`, `data/reports/` (commit `ce49f22`).
  - Quản lý repository nhóm (fork, mời collaborator).
- **Điều học được / Đóng góp chính:**
  - Cô lập các không gian vector để so sánh khách quan dữ liệu sạch, dữ liệu bẩn và dữ liệu đã phục hồi trên cùng một test set.

### ## NgoVanGiap-2A202602644
- **Vai trò:** Phụ trách Ingestion, Làm sạch & Corruption.
- **Công việc chi tiết đã hoàn thành:**
  - `src/ingestion/crossref.py`: parse payload Crossref (DOI, title, abstract bỏ thẻ JATS, authors, subject, ngày). Mặc định đọc snapshot offline, retry 429/5xx và fallback về snapshot.
  - `src/ingestion/cleaning.py`: chuẩn hóa text, tính `age_days`, dedupe theo `paper_id`, ghép `text_for_embedding` gồm 5 phần.
  - `src/ingestion/corruption.py`: 6 kịch bản lỗi (drop latest, blank summary, inject noise, truncate title, stale date, duplicate rows) với seed 42, ghi `data/results/corruption_log.json` (commit `53b5fec`).
- **Điều học được / Đóng góp chính:**
  - Data lineage: giữ nguyên raw snapshot trước mọi biến đổi để làm điểm neo phục hồi.

### ## HoangAnhTu-2A202602643
- **Vai trò:** Phụ trách Data Observability & Reporting.
- **Công việc chi tiết đã hoàn thành:**
  - Thiết lập Quality Gate chuẩn **Great Expectations 1.x** (Ephemeral Context) trong `src/observability/quality.py`, gồm 4 expectations: row count, not null, unique `paper_id`, độ dài summary.
  - Xây dựng `evaluate_freshness_sla` (tỉ lệ bài có `age_days > 180` không vượt quá 25%) và `build_freshness_report`.
  - Viết `src/observability/reporting.py` để sinh `phase1_report.md` và bảng đối chiếu 3 trạng thái trong `corruption_report.md` (commit `cf91356`).
- **Điều học được / Đóng góp chính:**
  - Thiết lập cảnh báo sớm để bắt silent failure trước khi dữ liệu vào serving layer. Gate bắt được blank summary, duplicate và stale date, nhưng bỏ lọt drop, noise và truncate; đây là hướng cần cải thiện.

### ## NguyenThanhNam-2A202602694
- **Vai trò:** Phụ trách Benchmark Evaluation Set.
- **Công việc chi tiết đã hoàn thành:**
  - Xây dựng `build_test_set` trong `src/evaluation/testset.py`: 10 câu hỏi trải đều corpus, gồm 4 dạng `summary` / `authors` / `date` / `categories`. Ground truth là DOI và trường tương ứng, lưu vào `data/eval/test_set.json` (commit `7be6a50`).
  - Đảm bảo test set có tính tất định và được dùng chung cho cả 3 trạng thái baseline, corrupted và repaired.
- **Điều học được / Đóng góp chính:**
  - Thiết kế test set ảnh hưởng trực tiếp đến kết luận: 8/10 câu có tài liệu bị phá nhưng chỉ 2 câu trả lời sai, nên metric trên test set đánh giá thấp mức thiệt hại.
