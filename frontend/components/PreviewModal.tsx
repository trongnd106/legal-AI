interface PreviewModalProps {
  open: boolean;
  title: string;
  content: string;
  onClose: () => void;
}

export function PreviewModal({ open, title, content, onClose }: PreviewModalProps) {
  if (!open) return null;

  return (
    <div
      className="modal-overlay"
      role="dialog"
      aria-modal="true"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="modal">
        <div className="modal-header">
          <h3>{title}</h3>
          <button className="modal-close" type="button" aria-label="Đóng" onClick={onClose}>
            &times;
          </button>
        </div>
        <div className="modal-body">{content}</div>
      </div>
    </div>
  );
}
