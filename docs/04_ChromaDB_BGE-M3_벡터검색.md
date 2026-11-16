# ChromaDB + BGE-M3 로컬 벡터 검색 — 개발 문서

| 항목 | 내용 |
|------|------|
| 상태 | **완료** (샘플 + 헤더 + 소스 RAG, 2026-11) |
| 목적 | few-shot·헤더 컨텍스트·관련 소스 검색을 의미 유사도로 보강 |
| 조합 | `chromadb` (임베디드 영구 저장) + `BAAI/bge-m3` (CPU 임베딩) |
| VRAM | 임베딩은 **CPU 전용**. 11GB VRAM은 `qwen3:14b`에 양보 |

---

## 1. 배경

기존 `samples_db.select_samples`는 키워드 매칭만 사용해, 표현이 다르면 관련 샘플을 놓칠 수 있었다.  
헤더·소스는 SQLite exact / 정규식에 의존해 이름 불일치·교차 파일 참조가 약했다.  
Docker 없는 경량 조합으로 ChromaDB + BGE-M3를 선택했다.

---

## 2. 아키텍처

```text
bug_samples.json ──► collection: bug_samples
SQLite symbols   ──► collection: header_symbols  (인덱싱 시 동기화)
project_root/**  ──► collection: source_chunks   (검토 시 ensure)

data/chroma/  PersistentClient
embedding: BAAI/bge-m3 @ CPU

검토 중 함수 청크
  ├─ select_samples     → few-shot (벡터 0.7 + 키워드 0.3)
  ├─ select_context     → exact → BGE 재순위 → chroma 보충 → regex
  └─ query_similar_sources → 프롬프트 [관련 소스 RAG]
```

주요 파일:

| 파일 | 역할 |
|------|------|
| `vector_store.py` | 3개 컬렉션 재구축/질의, CPU 임베딩 |
| `samples_db.py` | 하이브리드 few-shot |
| `symbol_index.py` | 헤더 인덱싱 후 Chroma 동기, select_context 병합 |
| `chunks.py` / `prompts.py` | 관련 소스 첨부 |
| `reviewer.py` | `prepare_review`에서 소스 인덱스 ensure |
| `app.py` | 옵션·헤더 UI, 재구축 버튼 |

---

## 3. 동작 규칙

1. **옵션 기본값**: 벡터 검색 **ON** (샘플·헤더·소스 공통 스위치)
2. 패키지 미설치·임베딩 실패 시 **자동 폴백** (검토 중단 없음)
3. 내용 해시가 같으면 재임베딩 생략
4. 소스 인덱스: 파일 최대 250, 청크 최대 400, 함수당 최대 80줄
5. 첫 실행 시 Hugging Face에서 `BAAI/bge-m3` 다운로드 가능

---

## 4. 설치

```bat
pip install -r requirements.txt
```

- `chromadb>=0.5.5`
- `sentence-transformers>=3.0.0`

확인: Streamlit → **옵션** → 샘플/헤더/소스 건수 및 재구축

영구 데이터: `data/chroma/` (`.gitignore`)

---

## 5. API 요약 (`vector_store.py`)

| 함수 | 설명 |
|------|------|
| `status` / `status_all` | 샘플·헤더·소스 상태 |
| `rebuild_sample_index` / `ensure_sample_index` | few-shot |
| `rebuild_header_symbol_index` / `ensure_header_symbol_index` | 헤더 |
| `query_similar_headers` | 헤더 벡터 검색 |
| `rebuild_source_chunk_index` / `ensure_source_chunk_index` | 소스 RAG |
| `query_similar_sources` | 소스 벡터 검색 |
| `rank_by_similarity` | 후보 재순위 |

---

## 6. 검증 체크리스트

- [ ] `pip install -r requirements.txt` 성공
- [ ] 옵션에서 샘플·헤더·소스 재구축 성공
- [ ] 벡터 OFF → 키워드·exact·정규식만 동작
- [ ] 헤더 인덱싱 후 Chroma 헤더 건수 증가
- [ ] 프로젝트 루트 검토 시 소스 RAG 청크·관련 소스 표시
- [ ] 검토 중 VRAM이 임베딩 때문에 늘지 않음 (CPU)
