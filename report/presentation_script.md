# Kịch Bản Thuyết Trình — Day 10: Data Pipeline & Data Observability

> **Thời lượng:** khoảng 4 phút 30 giây demo, sau đó Q&A.
> **Công cụ:** UI demo phong cách Brutalism — `python script/run_demo_ui.py`
>
> **Thông điệp chính** (nói ở đầu và nhắc lại ở cuối):
> **Dữ liệu hỏng không làm AI báo lỗi — nó làm AI trả lời sai trong im lặng. Chỉ Quality Gate mới bắt được, và bản gốc giúp hồi sinh.**

Cách đọc kịch bản: 🖥 = thao tác trên màn hình, 🎤 = lời nói (đọc tự nhiên, không cần thuộc từng chữ), 💡 = điểm cần nhấn mạnh.

---

## 0. Chuẩn bị (5 phút trước khi lên bảng)

- [ ] Chạy `python script/run_demo_ui.py`, trình duyệt mở http://127.0.0.1:8765
- [ ] **Tắt** công tắc "Dùng LLM Judge thật" — Gemini đang hết quota, bật lên thì mỗi phase có thể chạy hơn 10 phút
- [ ] Bấm **Chạy Phase 1** rồi **Chạy Phase 2** một lần để chắc chắn mọi thứ chạy (mỗi phase khoảng 2 giây)
- [ ] Mở sẵn tab thứ hai: http://127.0.0.1:8765/?ask=eval_009 (trang tự hỏi sẵn câu silent failure)
- [ ] Mở sẵn trong VS Code file `data/reports/corruption_report.md` (phương án dự phòng)
- [ ] **Đóng mọi file `.env`**, không để API key hiện trên màn hình chiếu
- [ ] Phóng to trình duyệt (`Ctrl` + `+`) để người ngồi cuối lớp đọc được

---

## Dòng thời gian

| # | Phần | Thời gian | Màn hình |
|---|---|---|---|
| 1 | Mở đầu | 0:00 – 0:30 | Đầu trang UI |
| 2 | Pipeline dữ liệu sạch | 0:30 – 1:15 | 01 Pipeline → Run Phase 1 |
| 3 | Quality Gate | 1:15 – 1:45 | 03 Quality Gate |
| 4 | Tiêm lỗi dữ liệu | 1:45 – 2:30 | Run Phase 2 → 04 Corruption Log |
| 5 | **Silent failure** | 2:30 – 3:45 | 02 Scoreboard → 06 Ask the RAG |
| 6 | Hồi sinh (repair) | 3:45 – 4:15 | Thẻ REPAIRED |
| 7 | Kết | 4:15 – 4:30 | — |

---

## 1. Mở đầu (30 giây)

🖥 Để ở đầu trang UI.

🎤 "Chào thầy cô và các bạn. Nhóm em xây một hệ thống RAG trả lời câu hỏi về 24 bài báo khoa học lấy từ Crossref.

Câu hỏi nhóm em muốn trả lời hôm nay là: **nếu dữ liệu đầu vào bị hỏng, AI có báo lỗi không?**

Câu trả lời là **không** — và đó chính là vấn đề. Nhóm em sẽ cho mọi người thấy dữ liệu hỏng âm thầm làm AI trả lời sai thế nào, cách phát hiện, và cách phục hồi."

---

## 2. Pipeline dữ liệu sạch (45 giây)

🖥 Bấm nút vàng **▶ Run Phase 1**, kéo xuống **01 Pipeline**. Chỉ tay vào từng ô khi nó chuyển sang màu đen (DONE ✓).

🎤 "Dữ liệu đi qua 6 phòng:

- **Ingest** — lấy metadata bài báo từ Crossref API và **lưu nguyên bản JSON gốc**. Bản gốc này là chìa khoá để phục hồi ở cuối bài. Nếu API lỗi hay bị chặn 429, pipeline tự đọc bản lưu offline nên không bao giờ bị gián đoạn.
- **Clean** — bỏ thẻ XML, bỏ khoảng trắng thừa, bỏ bản trùng, tính tuổi bài báo `age_days`, và ghép 5 trường thành một đoạn văn để tạo embedding.
- **Index** — biến mỗi bài thành vector bằng model MiniLM rồi lưu vào ChromaDB.
- **Testset** — 10 câu hỏi có đáp án chuẩn, chia 4 dạng: tóm tắt, tác giả, ngày xuất bản, lĩnh vực.
- **Evaluate** và **Gate** — chấm điểm AI và kiểm tra chất lượng dữ liệu."

🖥 Kéo xuống **02 Scoreboard**, chỉ vào thẻ **BASELINE**.

🎤 "Với dữ liệu sạch: Hit Rate 1.00, Token F1 1.00 — cả 10 câu đều đúng."

> Nếu có người hỏi thuật ngữ:
> - **Hit Rate** = tỉ lệ câu hỏi mà hệ thống tìm đúng bài báo trong top 4 kết quả.
> - **Token F1** = mức độ trùng từ giữa câu trả lời và đáp án chuẩn (1.00 = khớp hoàn toàn).

---

## 3. Quality Gate (30 giây)

🖥 Kéo xuống **03 Quality Gate**, chỉ vào cột **BASELINE**.

🎤 "Trước khi vào Vector DB, dữ liệu phải qua Quality Gate dựng bằng **Great Expectations 1.x**. Có 4 luật:

1. số dòng từ 5 đến 5000;
2. `paper_id`, `title`, `text_for_embedding` không được rỗng;
3. `paper_id` không được trùng;
4. tóm tắt dài ít nhất 30 ký tự.

Thêm một luật về **độ tươi**: không quá 25% số bài được cũ hơn 180 ngày.

Dữ liệu sạch qua hết 6/6 kiểm tra, chỉ 1 trên 24 bài là cũ — **cổng mở**."

---

## 4. Tiêm lỗi dữ liệu (45 giây)

🖥 Kéo lên, bấm nút hồng **▶ Run Phase 2**. Sau đó kéo xuống **04 Corruption Log**.

🎤 "Bây giờ nhóm em **cố tình phá dữ liệu**, mô phỏng 6 sự cố hay gặp ngoài thực tế:" *(chỉ vào từng thẻ)*

- "**Mất 5 bài mới nhất** — như job crawl bị dừng giữa chừng.
- **Xoá trắng 3 tóm tắt** và **chèn ký tự rác vào 3 tóm tắt** — như lỗi parse dữ liệu.
- **Cắt title** còn 7 ký tự, **lùi ngày** 6 bài về một năm trước, **nhân đôi** 3 dòng."

🖥 Bấm vào ô **E4 Truncate title** để lọc bảng bên dưới.

🎤 "Tổng cộng **20 trên 24 bài** bị động vào. Mỗi thay đổi đều được ghi vào nhật ký, kèm giá trị trước và sau — ví dụ title dài bị cắt thành `Advance`."

---

## 5. Silent failure — phần quan trọng nhất (75 giây)

🖥 Kéo lên **02 Scoreboard**, chỉ vào thẻ **CORRUPTED**.

🎤 "Đây là điểm đáng sợ. Pipeline chạy xong **không có một dòng lỗi nào**. 20 trên 24 bài bị hỏng, nhưng Hit Rate chỉ tụt từ 1.00 xuống 0.90. Nếu chỉ nhìn chỉ số, rất dễ nghĩ 'vẫn ổn'."

🖥 Chuyển sang tab **?ask=eval_009** (hoặc chọn `eval_009` trong **06 Ask the RAG**).

🎤 "Nhóm em hỏi cùng một câu cho cả 3 phiên bản dữ liệu. Bản CORRUPTED **vẫn tìm đúng bài báo** — nhãn HIT màu xanh — nhưng câu trả lời lại **rỗng**, vì tóm tắt đã bị xoá. Hệ thống không báo lỗi, chỉ lặng lẽ trả lời sai."

🖥 Kéo tới **05 Test Set**, chỉ vào dòng **004**.

🎤 "Câu 004 còn nguy hiểm hơn. Bài báo gốc đã bị xoá, nên hệ thống lấy **một bài khác** cùng lĩnh vực. Câu trả lời trông vẫn đúng, nhưng **nguồn thì sai** — người dùng không thể nào biết."

🖥 Kéo tới **03 Quality Gate**, chỉ vào cột **CORRUPTED**.

🎤 "Chỉ có Quality Gate phát hiện ra: 6 dòng trùng `paper_id`, 4 tóm tắt ngắn hơn 30 ký tự, và 31,8% bài đã cũ — vượt ngưỡng 25%. **Cổng đóng.**"

💡 "Đó là lý do cần Data Observability: **chỉ nhìn chỉ số của AI thì không đủ để phát hiện dữ liệu hỏng**."

---

## 6. Hồi sinh (30 giây)

🖥 Kéo lên **02 Scoreboard**, chỉ vào thẻ **REPAIRED**.

🎤 "Để sửa, nhóm em **không vá từng lỗi một**. Nhóm em dựng lại toàn bộ từ bản JSON gốc đã lưu ở bước Ingest — đây chính là **data lineage**.

Kết quả: 24 dòng, trùng khớp 100% với dữ liệu sạch, mọi chỉ số về lại 1.00, cổng mở lại.

Chạy repair bao nhiêu lần cũng ra cùng một kết quả — đó là tính **idempotent**."

---

## 7. Kết (15 giây)

🎤 "Nhóm em rút ra ba điều:

1. Dữ liệu hỏng làm AI sai **trong im lặng**.
2. Phải có **Quality Gate** và **Freshness SLA** canh ở cửa.
3. Luôn **giữ bản gốc** để có thể hồi sinh.

Em xin cảm ơn, mời thầy cô và các bạn đặt câu hỏi."

---

## Phương án dự phòng

| Sự cố | Cách xử lý |
|---|---|
| UI không mở được | Chạy trong terminal: `python script/run_phase1.py`, rồi `python script/run_corruption_flow.py`. Bảng 3 cột sẽ in ra console. Mở `data/reports/corruption_report.md` và bấm `Ctrl+Shift+V` để xem bản preview. |
| Mất mạng | Pipeline vẫn chạy nhờ snapshot offline, và model MiniLM đã được tải về máy. Chỉ có font chữ đổi sang serif mặc định. |
| Cổng 8765 đang bận | `python script/run_demo_ui.py --port 9000` |
| Terminal in tiếng Việt bị lỗi | Chạy `$env:PYTHONIOENCODING="utf-8"` trước |

---

## Chuẩn bị Q&A

**1. Tại sao dùng Great Expectations 1.x với Ephemeral Context?**
Ephemeral Context không cần tạo project GX trên ổ đĩa: mọi thứ nằm trong bộ nhớ, mỗi lần chạy đều sạch. Cú pháp 1.x đi theo chuỗi `data_sources.add_pandas` → `add_dataframe_asset` → `add_batch_definition_whole_dataframe` → `batch.validate(suite)`. Cú pháp cũ `ge.from_pandas` đã bị bỏ.

**2. Freshness SLA tính thế nào?**
`age_days = ngày chạy − ngày xuất bản`. Bài có `age_days > 180` bị coi là cũ. Nếu tỉ lệ bài cũ vượt 25% thì `is_fresh = False` và gate FAIL. Baseline có 1/24 bài cũ (4,2%). Corrupted có 7/22 (31,8%): 6 bài bị lùi ngày cộng 1 bài vốn đã cũ.

**3. 20/24 bài bị hỏng, sao Hit Rate chỉ giảm 10%?**
Thực ra 8/10 câu test có bài gốc bị phá, nhưng chỉ 2 câu trả lời sai. Lý do là câu trả lời chỉ hỏng khi lỗi trúng đúng trường được hỏi. Ví dụ `eval_005` hỏi summary, còn bài của nó chỉ bị lùi ngày, nên vẫn trả lời đúng. Hai câu sai là 004 (bài gốc bị xoá, retrieval miss) và 009 (hỏi summary đúng lúc summary bị xoá trắng). Đây chính là bài học: metric trên test set đánh giá thấp thiệt hại, nên phải kiểm tra ngay ở tầng dữ liệu.

**4. Tại sao gate báo 6 dòng trùng và 4 tóm tắt ngắn, mà lỗi tiêm vào chỉ có 3?**
Nhân đôi 3 dòng thì có 6 dòng mang `paper_id` trùng (tính cả bản gốc lẫn bản sao). Một trong các dòng bị nhân đôi lại là dòng đã bị xoá trắng tóm tắt, nên có 3 + 1 = 4 tóm tắt rỗng.

**5. Embedding là gì? Sao chọn MiniLM?**
Embedding biến văn bản thành vector số, để các câu gần nghĩa nằm gần nhau. Model `all-MiniLM-L6-v2` cho vector 384 chiều; nó nhỏ, chạy được trên CPU và miễn phí. ChromaDB tìm tài liệu bằng cosine similarity.

**6. Idempotent nghĩa là gì trong bài này?**
Chạy nhiều lần vẫn cho cùng một kết quả. Hàm repair chỉ phụ thuộc vào raw snapshot, không phụ thuộc trạng thái đang hỏng. Mỗi lần index, collection được xoá rồi tạo lại, nên không bị "vector ma" sót lại từ lần chạy trước.

**7. Tại sao phải lưu dữ liệu raw?**
Raw là điểm neo lineage. Khi phục hồi không cần gọi lại API, nên tránh được rate limit, và nguồn sống có thay đổi thì bản gốc vẫn giữ nguyên.

**8. Tại sao dùng 3 collection ChromaDB riêng?**
Để so sánh công bằng: cùng test set, cùng model, cùng cách chấm, chỉ khác mỗi dữ liệu.

**9. Judge Accuracy có dùng LLM không?**
Code hỗ trợ LLM Judge qua Gemini, dùng structured output. Hiện Gemini đang hết quota, nên judge tự chuyển sang heuristic theo Token F1: từ 0,95 trở lên được 5 điểm, từ 0,5 trở lên được 3 điểm, còn lại 1 điểm. Hit Rate và Token F1 không phụ thuộc LLM. *(Trả lời trung thực, đừng nói là LLM chấm.)*

**10. Trong production, dữ liệu bẩn có được đưa vào index không?**
Trong demo, nhóm cố tình cho dữ liệu bẩn đi tiếp để đo được tác hại. Hướng phát triển cho production: gate FAIL thì dừng không index, giữ collection cũ đang phục vụ, rồi tự kích hoạt repair.

**11. Đổi LLM provider thế nào?**
Sửa `LLM_PROVIDER` trong `.env`. Các giá trị hỗ trợ: `gemini`, `openai`, `anthropic`, `openrouter`, `ollama`, `custom`, `mock`.

**12. UI này để làm gì?**
Đây là dashboard observability tương tác (mục bonus B1 trong rubric). Nó hiển thị Quality Gate, Freshness, so sánh 3 trạng thái và nhật ký lỗi, cho phép hỏi RAG trực tiếp trên cả 3 collection, và chạy pipeline ngay trên giao diện.

**13. Hỏi câu nằm ngoài corpus thì hệ thống trả lời thế nào?**
Hệ thống trả lời "I don't know from the indexed corpus.". Ban đầu, pipeline luôn lấy bài đứng đầu kết quả tìm kiếm để trích câu trả lời. Vì vậy câu "Who authored the paper about cooking pasta?" nhận được một cặp tên tác giả bịa ra. Nhóm đã thêm ngưỡng độ giống cosine 0.3 cho kết quả top-1 (`MIN_RELEVANCE_SCORE` trong `src/retrieval/qa.py`). Ngưỡng này được đặt theo số đo thực tế: câu trong test set có score ≥ 0.53, câu ngoài domain chỉ ≤ 0.14. Metric của cả 3 trạng thái không đổi. *(Có thể demo trực tiếp ở phần hỏi RAG của UI.)*

---

## Bảng số liệu (để tra nhanh khi bị hỏi)

| Chỉ số | Baseline | Corrupted | Repaired |
|---|---|---|---|
| Retrieval Hit Rate | 1.00 | 0.90 | 1.00 |
| Mean Token F1 | 1.00 | 0.90 | 1.00 |
| Judge Accuracy | 1.00 | 0.90 | 1.00 |
| Mean Judge Score (1–5) | 5.0 | 4.6 | 5.0 |
| Số dòng | 24 | 22 | 24 |
| Expectations đạt | 6/6 | 4/6 | 6/6 |
| Tỉ lệ bài cũ (> 180 ngày) | 4,2% | 31,8% | 4,2% |
| Quality Gate | PASS | **FAIL** | PASS |

Nguồn: `data/results/*_metrics.json`, `data/quality/*_quality_report.json`. Nếu chạy lại pipeline vào một ngày khác, `age_days` sẽ thay đổi; hãy đối chiếu lại bảng này trước khi lên bảng.
