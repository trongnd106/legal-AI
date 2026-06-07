"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Mic, Paperclip, Send, Sparkles } from "lucide-react";
import { escapeHtml, sendChatMessage } from "@/lib/api";
import type { ChatMessage } from "@/types/api";
import { MarkdownMessage } from "./MarkdownMessage";
import { useToast } from "./ToastProvider";

function formatMessageTime(ts: number): string {
  const d = new Date(ts);
  const h = String(d.getHours()).padStart(2, "0");
  const m = String(d.getMinutes()).padStart(2, "0");
  const s = String(d.getSeconds()).padStart(2, "0");
  return `${h}:${m}:${s}`;
}

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

interface ChatPanelProps {
  sessionId: string;
  messages: ChatMessage[];
  loading?: boolean;
  onMessagesChange: (
    sessionId: string,
    updater: ChatMessage[] | ((prev: ChatMessage[]) => ChatMessage[]),
  ) => void;
  onFirstUserMessage: (sessionId: string, text: string) => void;
}

export function ChatPanel({
  sessionId,
  messages,
  loading = false,
  onMessagesChange,
  onFirstUserMessage,
}: ChatPanelProps) {
  const { showToast } = useToast();
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [typing, setTyping] = useState(false);
  const [attachedFile, setAttachedFile] = useState<File | null>(null);
  const [recording, setRecording] = useState(false);
  const [micSupported, setMicSupported] = useState(true);

  const messagesRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const recognitionRef = useRef<SpeechRecognition | null>(null);

  const setMessages = useCallback(
    (updater: ChatMessage[] | ((prev: ChatMessage[]) => ChatMessage[])) => {
      onMessagesChange(sessionId, updater);
    },
    [sessionId, onMessagesChange],
  );

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

    onFirstUserMessage(sessionId, question);

    let displayQ = question;
    if (attachedFile) displayQ += `\n\n📎 ${attachedFile.name}`;

    setMessages((prev) => [
      ...prev,
      {
        role: "user",
        html: `<p>${escapeHtml(displayQ).replace(/\n/g, "<br>")}</p>`,
        timestamp: Date.now(),
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
          timestamp: Date.now(),
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
          timestamp: Date.now(),
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
        {loading && (
          <div className="session-loading">Đang tải cuộc trò chuyện...</div>
        )}
        {!loading && messages.map((msg, idx) => (
          <div key={idx} className={`message ${msg.role}`}>
            {msg.role === "bot" ? (
              <>
                <div className="avatar bot-avatar">🤖</div>
                <div className="message-body">
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
                  {msg.timestamp != null && (
                    <time
                      className="message-time"
                      dateTime={new Date(msg.timestamp).toISOString()}
                    >
                      {formatMessageTime(msg.timestamp)}
                    </time>
                  )}
                </div>
              </>
            ) : (
              <>
                <div className="message-body">
                  <div className="bubble user-bubble">
                    {msg.html ? (
                      <div dangerouslySetInnerHTML={{ __html: msg.html }} />
                    ) : null}
                  </div>
                  {msg.timestamp != null && (
                    <time
                      className="message-time"
                      dateTime={new Date(msg.timestamp).toISOString()}
                    >
                      {formatMessageTime(msg.timestamp)}
                    </time>
                  )}
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
          className="icon-btn"
          type="button"
          title="Đính kèm file"
          onClick={() => fileInputRef.current?.click()}
        >
          <Paperclip size={20} aria-hidden />
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
        <div className="input-right-group">
          <button
            className={`icon-btn${recording ? " recording" : ""}`}
            type="button"
            title={
              micSupported
                ? "Gửi bằng giọng nói"
                : "Trình duyệt không hỗ trợ nhận dạng giọng nói"
            }
            disabled={!micSupported}
            onClick={startMic}
          >
            <Mic size={20} aria-hidden />
          </button>
          <button
            className="icon-btn"
            type="button"
            title="Gợi ý AI"
            onClick={() => showToast("Tính năng gợi ý AI đang được phát triển")}
          >
            <Sparkles size={18} aria-hidden />
          </button>
          <button
            className="btn-send-grid"
            type="button"
            title="Gửi"
            disabled={sending}
            onClick={() => void handleSend()}
          >
            <Send size={18} aria-hidden />
          </button>
        </div>
      </div>
    </>
  );
}
