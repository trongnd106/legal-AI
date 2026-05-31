"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  downloadDocumentUrl,
  fileTypeIcon,
  formatBytes,
  formatDate,
  listDocuments,
  previewDocument,
  uploadDocument,
} from "@/lib/api";
import type { DocumentItem } from "@/types/api";
import { PreviewModal } from "./PreviewModal";
import { useToast } from "./ToastProvider";

function StatusBadge({ tinhTrang }: { tinhTrang: string }) {
  if (tinhTrang === "con_hieu_luc") {
    return <span className="file-status active">Còn hiệu lực</span>;
  }
  if (tinhTrang === "het_hieu_luc") {
    return <span className="file-status expired">Hết hiệu lực</span>;
  }
  return null;
}

export function DocumentPanel() {
  const { showToast } = useToast();
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dragover, setDragover] = useState(false);
  const [preview, setPreview] = useState<{ title: string; content: string } | null>(
    null,
  );

  const uploadInputRef = useRef<HTMLInputElement>(null);

  const loadDocuments = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listDocuments();
      setDocuments(data.documents || []);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Lỗi tải dữ liệu";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadDocuments();
  }, [loadDocuments]);

  const handleUpload = async (file: File) => {
    showToast(`Đang tải lên ${file.name}...`);
    try {
      const result = await uploadDocument(file);
      showToast(result.message || "Tải lên thành công");
      await loadDocuments();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Tải lên thất bại";
      showToast(message, true);
    }
  };

  const openPreview = async (doc: DocumentItem) => {
    setPreview({ title: doc.ten, content: "Đang tải..." });
    try {
      const data = await previewDocument(doc.id);
      setPreview({ title: doc.ten, content: data.content || "(Không có nội dung)" });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Lỗi";
      setPreview({ title: doc.ten, content: `Lỗi: ${message}` });
    }
  };

  return (
    <>
      <div className="panel-content">
        <div
          className={`upload-zone${dragover ? " dragover" : ""}`}
          role="button"
          tabIndex={0}
          onClick={() => uploadInputRef.current?.click()}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              uploadInputRef.current?.click();
            }
          }}
          onDragOver={(e) => {
            e.preventDefault();
            setDragover(true);
          }}
          onDragLeave={() => setDragover(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragover(false);
            const file = e.dataTransfer?.files?.[0];
            if (file) void handleUpload(file);
          }}
        >
          <input
            ref={uploadInputRef}
            type="file"
            accept=".txt,.pdf,.doc,.docx"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) void handleUpload(file);
              e.target.value = "";
            }}
          />
          <div className="upload-zone-inner">
            <div className="upload-icon">
              <span className="file-icon-emoji">📄</span>
              <span className="up-arrow">⬆</span>
            </div>
            <div>
              <div className="upload-label">Tải lên file luật mới</div>
              <div className="upload-hint">TXT, PDF, DOCX — kéo thả hoặc bấm để chọn</div>
            </div>
          </div>
        </div>

        <div className="panel-toolbar">
          <h2>Văn bản pháp luật</h2>
          <span className="panel-count">
            {loading ? "Đang tải..." : error ? "Lỗi tải dữ liệu" : `${documents.length} văn bản`}
          </span>
        </div>

        <div className="file-grid">
          {loading && <div className="panel-loading">Đang tải danh sách văn bản...</div>}
          {!loading && error && <div className="panel-empty">⚠️ {error}</div>}
          {!loading && !error && documents.length === 0 && (
            <div className="panel-empty">Chưa có văn bản. Tải lên file luật mới ở trên.</div>
          )}
          {!loading &&
            !error &&
            documents.map((doc) => {
              const { emoji, cls } = fileTypeIcon(doc.extension);
              return (
                <div key={doc.id} className="file-card">
                  <div className={`file-icon ${cls}`}>{emoji}</div>
                  <div className="file-info">
                    <div className="file-name" title={doc.ten}>
                      {doc.ten}
                    </div>
                    <div className="file-meta">
                      {formatBytes(doc.size_bytes)} •{" "}
                      {formatDate(doc.ngay_hieu_luc || doc.updated_at)}
                    </div>
                    <StatusBadge tinhTrang={doc.tinh_trang} />
                  </div>
                  <div className="file-actions">
                    <button
                      className="file-btn"
                      type="button"
                      title="Tải xuống"
                      onClick={() => window.open(downloadDocumentUrl(doc.id), "_blank")}
                    >
                      ⬇️
                    </button>
                    <button
                      className="file-btn"
                      type="button"
                      title="Xem"
                      onClick={() => void openPreview(doc)}
                    >
                      👁️
                    </button>
                  </div>
                </div>
              );
            })}
        </div>
      </div>

      <PreviewModal
        open={preview !== null}
        title={preview?.title ?? ""}
        content={preview?.content ?? ""}
        onClose={() => setPreview(null)}
      />
    </>
  );
}
