# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Họ và tên       | Đinh Bảo Hưng             |
| MSSV               | 2A202602524                     |
| Khóa/Lớp         | K4-L3B              |
| Tên nhóm         | fanboiPNV     |
| Vai trò chính    | Embedding/vector index & artifact owner                 |
| Repository         | https://github.com/hungdinh2611/K4-L3B-Day10-fanboiPNV-Data-Pipeline-Data-Observability |
| Ngày hoàn thành | 2026-09-26               |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao  | Trạng thái                                 |
| ------------------ | --------------------- | ---------------- | ----------------- | -------------------------------------------- |
| Vector index 3 trạng thái | `LocalEmbeddingIndex.build` (`src/retrieval/index.py`, starter), gọi từ 2 pipeline | Clean / corrupted / repaired dataframe | `data/chroma/`, `data/embeddings/papers_embeddings*.json` | Hoàn thành |
| Bộ artifact bằng chứng | Toàn bộ `data/` sinh ra khi chạy pipeline | Output của Phase 1 & 2 | `data/eval/`, `data/quality/`, `data/results/`, `data/reports/` (commit `ce49f22`) | Hoàn thành |
| Quản lý repository | GitHub `hungdinh2611/...` | Repo mẫu | Fork, mời collaborator | Hoàn thành |

Hai pipeline của Trung ghi artifact vào `data/`. Phần tôi phụ trách là bảo đảm các artifact đó có mặt đầy đủ trên repo để giảng viên đối chiếu với báo cáo.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                         | Thành viên/module được hỗ trợ | Kết quả                    |
| ------------------------------------ | ------------------------------------ | ---------------------------- |
| Chạy lại pipeline để kiểm tra kết quả tích hợp | Trung (orchestration) | Metrics khớp giữa các lần chạy |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao       | Cách xác minh         |
| --------------------------- | ----------------------------- | ------------------------- | ----------------------- |
| Index 24 tài liệu với MiniLM, cosine | `data/embeddings/papers_embeddings.json` | Collection `papers-baseline`, 24 documents | Đọc manifest: `collection_name`, `len(documents)` |
| Tách 3 collection | `papers-baseline`, `papers-corrupted`, `papers-repaired` | 3 manifest riêng | `data/embeddings/*.json` |
| Commit artifacts | `data/` | 60 file (commit `ce49f22`) | `git show --stat ce49f22` |

Nêu một output cụ thể mà phần việc của bạn tạo ra hoặc giúp xác minh:

`data/embeddings/papers_embeddings.json`: backend `chroma`, model `sentence-transformers/all-MiniLM-L6-v2`, collection `papers-baseline`, 24 documents kèm metadata (paper_id, title, published, authors, categories, summary).

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Để đo tác động của dữ liệu lên RAG, mỗi trạng thái dữ liệu phải có không gian vector riêng. Không được để vector của dữ liệu bẩn lẫn vào dữ liệu sạch.

### Cách triển khai

- Mỗi trạng thái được ghi vào một collection riêng; tên collection lấy từ đường dẫn manifest (`_derive_collection_name`).
- Trước khi build, collection cũ bị xóa và tạo lại (`delete_collection` → `create_collection`), nên không còn "vector ma" từ lần chạy trước.
- Embedding được normalize, và ChromaDB dùng `hnsw:space = cosine`.
- `record_id = <paper_id>::<index>`, để dữ liệu bẩn có dòng trùng `paper_id` vẫn index được. Điều này cho phép đo đúng tác hại của duplicate thay vì để pipeline lỗi.

### Input, output và contract

| Thành phần                   | Mô tả                                     |
| ------------------------------ | ------------------------------------------- |
| Input                          | DataFrame có `paper_id`, `title`, `text_for_embedding`, `published`, `authors_joined`, `categories_joined`, `summary`, `abs_url`, `pdf_url` |
| Output                         | Collection ChromaDB + manifest JSON (`backend`, `embedding_model`, `persist_path`, `collection_name`, `documents`) |
| Module phụ thuộc             | `ingestion.cleaning` (schema), `retrieval.embeddings` |
| Module sử dụng output        | `retrieval.qa`, `evaluation.metrics`, `demo_ui` |
| Điều kiện lỗi cần xử lý | Collection đã tồn tại; `paper_id` trùng trong dữ liệu bẩn |

### Cách xác minh

```bash
python script/run_phase1.py
python -c "import json; d=json.load(open('data/embeddings/papers_embeddings.json')); print(d['collection_name'], len(d['documents']))"
```

- **Kết quả mong đợi:** `papers-baseline 24`
- **Kết quả thực tế:** `papers-baseline 24`. Corrupted có 22 documents (có dòng trùng), repaired có 24.
- **Artifact/log:** `data/embeddings/`, `data/chroma/`

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Lưu 3 trạng thái dữ liệu trong vector store.
- **Các phương án đã cân nhắc:**
  - (1) Dùng một collection và ghi đè mỗi lần.
  - (2) Dùng một collection, phân biệt bằng metadata `stage`.
  - (3) Dùng 3 collection riêng.
- **Phương án đã chọn:** (3).
- **Lý do:**
  - (1) làm mất baseline, không so sánh được.
  - (2) phải lọc trong mọi truy vấn, và dễ bị rò: truy vấn quên filter sẽ trộn dữ liệu bẩn.
  - (3) cô lập hoàn toàn, và demo UI hỏi được song song cả 3 trạng thái.
- **Bằng chứng quyết định phù hợp:** Cùng câu hỏi `eval_009`, collection corrupted trả lời rỗng trong khi baseline và repaired trả lời đúng.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Manifest `data/embeddings/papers_embeddings.json` chứa `"persist_path": "H:\\AI2026\\K4-L3B-Day10-fanboiPNV-Data-Pipeline-Data-Observability\\data\\chroma"`, là đường dẫn tuyệt đối trên máy cá nhân.
- **Lệnh hoặc bước tái hiện:** Chạy `run_phase1.py`, sau đó mở manifest.
- **Nguyên nhân gốc:** `LocalEmbeddingIndex.build` (starter) ghi `str(persist_path)` tuyệt đối, và `LocalEmbeddingIndex.load` đọc lại đúng giá trị này.
- **Cách xử lý:** Chưa sửa trong code starter. Hai pipeline luôn build lại index từ `settings.paths.chroma_dir`, nên kết quả chấm không bị ảnh hưởng.

Nếu chưa xử lý xong:

- **Phạm vi bị ảnh hưởng:** `LocalEmbeddingIndex.load` và demo UI khi chạy trên máy khác mà chưa chạy lại pipeline.
- **Những gì đã loại trừ:** Hai lệnh `run_phase1.py` và `run_corruption_flow.py` không dùng `load`, nên không bị ảnh hưởng.
- **Bước tiếp theo:** Lưu `persist_path` dạng tương đối so với `project_dir`, hoặc bỏ qua giá trị này khi load và luôn dùng `settings.paths.chroma_dir`. Kiểm tra bằng cách clone repo sang thư mục khác rồi mở demo UI.

## 7. Hiểu biết về luồng end-to-end

**Câu trả lời:**

1. **Từ Crossref đến vector index:** Raw JSON từ Crossref được parse và clean. Mỗi dòng có một đoạn `text_for_embedding` 5 phần, được MiniLM encode thành vector 384 chiều rồi đưa vào ChromaDB kèm metadata.
2. **Đo chất lượng:** Câu hỏi được embed để tìm top 4 tài liệu. Có ground-truth DOI trong đó thì tính là hit. Câu trả lời được so với đáp án bằng Token F1.
3. **Quality checks và freshness:** Quality checks xem dữ liệu có hợp lệ không (null, trùng, độ dài). Freshness xem dữ liệu có còn mới không (tuổi bài báo).
4. **Cùng test set:** Nếu câu hỏi thay đổi theo từng trạng thái thì không biết metric thay đổi là do dữ liệu hay do câu hỏi.
5. **Repair thành công khi:** Collection `papers-repaired` có lại 24 documents, gate 6/6, và metric bằng baseline.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` |      1.00 |       0.90 |      1.00 | Miss ở `eval_004` vì tài liệu không còn trong collection |
| `mean_token_f1`      |      1.00 |       0.90 |      1.00 | Retrieval vẫn đúng ở `eval_009`, nhưng nội dung đã rỗng |
| `judge_accuracy`     |      1.00 |       0.90 |      1.00 | — |
| `mean_judge_score`   |      5.00 |       4.60 |      5.00 | — |
| Quality checks         |      6/6 |       4/6 |      6/6 | Trùng `paper_id` vẫn index được nhờ `record_id` có số thứ tự |
| Freshness status       |      Fresh |       Stale |      Fresh | — |

### Kết luận từ số liệu

1. Drop latest xóa bài `…3671808` khỏi collection → gate không báo (22 dòng vẫn hợp lệ) → `eval_004` retrieval miss, Hit Rate 0.90.
2. Index lại `papers-repaired` từ dữ liệu repair → 24 documents, gate PASS → Hit Rate 1.00.

Corruption nào ảnh hưởng rõ nhất và vì sao?

Từ góc nhìn retrieval là drop latest: tài liệu không còn trong index thì không thể tìm được, và câu trả lời lấy từ bài khác, đúng về nội dung nhưng sai nguồn.

Kết quả nào khác với kỳ vọng ban đầu?

Truncate title không làm miss câu `eval_002`. Semantic search vẫn tìm được bài nhờ phần authors và summary trong `text_for_embedding`, dù lookup chính xác theo title thất bại.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Artifact phải được commit đầy đủ thì kết quả mới kiểm chứng được.
2. Gate cần một check về số lượng tài liệu so với lần trước, vì row count tuyệt đối không bắt được việc mất 20% dữ liệu.
3. Embedding gộp nhiều trường giúp retrieval chịu lỗi tốt hơn: title bị cắt vẫn tìm ra bài.

### Nếu có thêm thời gian

Sửa `persist_path` sang đường dẫn tương đối và thêm check "số document trong collection ≥ 90% lần trước". Đo bằng cách chạy lại corruption flow và kỳ vọng check này FAIL khi gặp lỗi drop latest.

## 10. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [ ] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [ ] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [ ] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [ ] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [ ] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [ ] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Đinh Bảo Hưng
**Ngày xác nhận:** [YYYY-MM-DD]
