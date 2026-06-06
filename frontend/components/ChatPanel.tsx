"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { escapeHtml, sendChatMessage } from "@/lib/api";
import type { ChatMessage } from "@/types/api";
import { MarkdownMessage } from "./MarkdownMessage";
import { useToast } from "./ToastProvider";

const WELCOME_HTML = `
  <p>Xin chào! Tôi là trợ lý tư vấn <strong>Luật Lao động Việt Nam</strong>.</p>
  <p>Tôi có thể hỗ trợ bạn tra cứu Bộ luật Lao động 2019 và các Nghị định hướng dẫn.</p>
  <ul>
    <li>Quyền và nghĩa vụ của người lao động</li>
    <li>Hợp đồng lao động, thử việc, chấm dứt HĐLĐ</li>
    <li>Lương, BHXH, thời giờ làm việc, nghỉ phép</li>
  </ul>
`;

const INITIAL_MESSAGES: ChatMessage[] = [
  { role: "bot", html: WELCOME_HTML, plain: "Xin chào!" },
];

function copyText(text: string, showToast: (msg: string, err?: boolean) => void) {
  navigator.clipboard.writeText(text).then(
    () => showToast("Đã sao chép vào clipboard"),
    () => showToast("Không sao chép được", true),
  );
}

function downloadText(text: string, idx: number) {
  const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `luat-lao-dong-ai-${idx + 1}.txt`;
  a.click();
  URL.revokeObjectURL(a.href);
}

export function ChatPanel() {
  const { showToast } = useToast();
  const [messages, setMessages] = useState<ChatMessage[]>(INITIAL_MESSAGES);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [typing, setTyping] = useState(false);
  const [attachedFile, setAttachedFile] = useState<File | null>(null);
  const [recording, setRecording] = useState(false);
  const [micSupported, setMicSupported] = useState(true);

  const messagesRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const recognitionRef = useRef<SpeechRecognition | null>(null);

  useEffect(() => {
    const el = messagesRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, typing]);

  useEffect(() => {
    const SpeechRecognitionCtor =
      window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognitionCtor) {
      setMicSupported(false);
      return;
    }

    const recognition = new SpeechRecognitionCtor();
    recognition.lang = "vi-VN";
    recognition.interimResults = false;
    recognition.onstart = () => setRecording(true);
    recognition.onend = () => setRecording(false);
    recognition.onerror = () => {
      setRecording(false);
      showToast("Không nhận dạng được giọng nói", true);
    };
    recognition.onresult = (e) => {
      const transcript = e.results[0][0].transcript;
      setInput((prev) => (prev + " " + transcript).trim());
    };
    recognitionRef.current = recognition;
  }, [showToast]);

  const clearAttachment = useCallback(() => {
    setAttachedFile(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }, []);

  const handleSend = async () => {
    const question = input.trim();
    if (!question || sending) return;

    let displayQ = question;
    if (attachedFile) displayQ += `\n\n📎 ${attachedFile.name}`;

    setMessages((prev) => [
      ...prev,
      {
        role: "user",
        html: `<p>${escapeHtml(displayQ).replace(/\n/g, "<br>")}</p>`,
      },
    ]);
    setInput("");
    setSending(true);
    setTyping(true);

    try {
      const mode = question.length > 120 ? "global" : "local";
      const data = await sendChatMessage({ question, mode, domain: "lao_dong" });
      const answer = data.answer || "Không có câu trả lời.";
      setMessages((prev) => [
        ...prev,
        {
          role: "bot",
          markdown: answer,
          plain: answer,
          citations: data.article_citations || [],
          dataCitations: data.data_citations || [],
        },
      ]);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Lỗi khi gửi câu hỏi.";
      setMessages((prev) => [
        ...prev,
        {
          role: "bot",
          html: `<p>⚠️ ${escapeHtml(message)}</p>`,
          plain: message,
        },
      ]);
    } finally {
      setTyping(false);
      setSending(false);
      clearAttachment();
    }
  };

  const startMic = () => {
    try {
      recognitionRef.current?.start();
    } catch {
      showToast("Mic đang bật hoặc không khả dụng", true);
    }
  };

  return (
    <>
      <div ref={messagesRef} className="chat-messages" aria-live="polite">
        {messages.map((msg, idx) => (
          <div key={idx} className={`message ${msg.role}`}>
            {msg.role === "bot" ? (
              <>
                <div className="avatar bot-avatar">🤖</div>
                <div className="bubble bot-bubble">
                  {msg.markdown ? (
                    <MarkdownMessage
                      content={msg.markdown}
                      dataCitations={msg.dataCitations}
                    />
                  ) : msg.html ? (
                    <div dangerouslySetInnerHTML={{ __html: msg.html }} />
                  ) : null}
                  {msg.citations && msg.citations.length > 0 && (
                    <div className="bubble-citations">
                      Căn cứ: {msg.citations.join(", ")}
                    </div>
                  )}
                  {msg.plain && (
                    <div className="bubble-actions">
                      <button
                        className="action-btn"
                        type="button"
                        onClick={() => copyText(msg.plain!, showToast)}
                      >
                        <span>📋</span> Sao chép
                      </button>
                      <button
                        className="action-btn"
                        type="button"
                        onClick={() => downloadText(msg.plain!, idx)}
                      >
                        <span>⬇️</span> Tải về file
                      </button>
                    </div>
                  )}
                </div>
              </>
            ) : (
              <>
                <div className="bubble user-bubble">
                  {msg.html ? (
                    <div dangerouslySetInnerHTML={{ __html: msg.html }} />
                  ) : null}
                </div>
                <div className="avatar user-avatar">👤</div>
              </>
            )}
          </div>
        ))}

        {typing && (
          <div className="message bot">
            <div className="avatar bot-avatar">🤖</div>
            <div className="bubble bot-bubble">
              <div className="typing-indicator">
                <span />
                <span />
                <span />
              </div>
            </div>
          </div>
        )}
      </div>

      {attachedFile && (
        <div className="attach-preview">
          📎 Đính kèm: {attachedFile.name} (chỉ tham khảo ngữ cảnh — hỏi đáp vẫn dựa trên
          kho luật)
        </div>
      )}

      <div className="chat-input-bar">
        <input
          ref={fileInputRef}
          type="file"
          accept=".txt,.pdf,.doc,.docx"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) setAttachedFile(file);
          }}
        />
        <button
          className="input-icon-btn"
          type="button"
          title="Đính kèm"
          onClick={() => fileInputRef.current?.click()}
        >
          📎
        </button>
        <input
          type="text"
          className="chat-input"
          placeholder="Nhập câu hỏi về luật lao động của bạn tại đây..."
          autoComplete="off"
          value={input}
          disabled={sending}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void handleSend();
            }
          }}
        />
        <button
          className={`input-icon-btn${recording ? " recording" : ""}`}
          type="button"
          title={micSupported ? "Giọng nói" : "Trình duyệt không hỗ trợ nhận dạng giọng nói"}
          disabled={!micSupported}
          onClick={startMic}
        >
          🎤
        </button>
        <button
          className="btn-send"
          type="button"
          title="Gửi"
          disabled={sending}
          onClick={() => void handleSend()}
        >
          ➤
        </button>
      </div>
    </>
  );
}
