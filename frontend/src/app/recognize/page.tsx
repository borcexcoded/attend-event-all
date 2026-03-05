"use client";

import { useRef, useState, useCallback } from "react";
import { recognizeFaces, type RecognitionResult } from "@/lib/api";

export default function RecognizePage() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [streaming, setStreaming] = useState(false);
  const [result, setResult] = useState<RecognitionResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [preview, setPreview] = useState<string | null>(null);

  const startCamera = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user", width: 640, height: 480 },
      });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        setStreaming(true);
        setError("");
      }
    } catch {
      setError(
        "Could not access camera. Please allow camera permissions or upload a photo instead."
      );
    }
  }, []);

  const stopCamera = useCallback(() => {
    if (videoRef.current?.srcObject) {
      const stream = videoRef.current.srcObject as MediaStream;
      stream.getTracks().forEach((track) => track.stop());
      videoRef.current.srcObject = null;
      setStreaming(false);
    }
  }, []);

  const captureAndRecognize = useCallback(async () => {
    if (!videoRef.current || !canvasRef.current) return;

    const canvas = canvasRef.current;
    const video = videoRef.current;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(video, 0, 0);

    setPreview(canvas.toDataURL("image/jpeg"));

    canvas.toBlob(async (blob) => {
      if (!blob) return;
      const file = new File([blob], "capture.jpg", { type: "image/jpeg" });
      await processRecognition(file);
    }, "image/jpeg", 0.9);
  }, []);

  const handleFileUpload = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;

      const reader = new FileReader();
      reader.onload = (ev) => setPreview(ev.target?.result as string);
      reader.readAsDataURL(file);

      await processRecognition(file);
    },
    []
  );

  async function processRecognition(file: File) {
    setLoading(true);
    setError("");
    setResult(null);

    try {
      const data = await recognizeFaces(file);
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Recognition failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-10">
      {/* Header */}
      <div>
        <h1 className="text-[34px] font-bold tracking-[-0.03em] text-foreground">
          Take Attendance
        </h1>
        <p className="text-[15px] text-foreground-secondary mt-1">
          Use your camera or upload a group photo to mark attendance.
        </p>
      </div>

      {error && (
        <div className="bg-danger-light border border-danger/20 rounded-2xl p-5 flex items-start gap-3">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-danger flex-shrink-0 mt-0.5">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          <p className="text-[14px] text-danger">{error}</p>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Camera / Upload Section */}
        <div className="bg-card border border-divider rounded-2xl p-7 shadow-[var(--shadow-sm)]">
          <h2 className="text-[17px] font-semibold tracking-[-0.01em] mb-5 flex items-center gap-2.5">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="text-foreground-secondary">
              <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
              <circle cx="12" cy="13" r="4" />
            </svg>
            Capture
          </h2>

          {/* Video preview */}
          <div className="relative bg-background-secondary rounded-xl overflow-hidden mb-5 aspect-video border border-divider">
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className={`w-full h-full object-cover ${streaming ? "block" : "hidden"}`}
            />
            {preview && !streaming && (
              <img
                src={preview}
                alt="Captured"
                className="w-full h-full object-cover"
              />
            )}
            {!streaming && !preview && (
              <div className="absolute inset-0 flex flex-col items-center justify-center text-foreground-secondary">
                <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.2" className="mb-3 opacity-40">
                  <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
                  <circle cx="12" cy="13" r="4" />
                </svg>
                <p className="text-[14px]">Start camera or upload a photo</p>
              </div>
            )}
          </div>

          <canvas ref={canvasRef} className="hidden" />

          <div className="flex flex-wrap gap-3">
            {!streaming ? (
              <button
                onClick={startCamera}
                className="px-5 py-2.5 bg-primary text-white text-[14px] font-medium rounded-xl hover:bg-primary-hover transition-colors duration-200"
              >
                Start Camera
              </button>
            ) : (
              <>
                <button
                  onClick={captureAndRecognize}
                  disabled={loading}
                  className="px-5 py-2.5 bg-success text-white text-[14px] font-medium rounded-xl hover:opacity-90 transition-all duration-200 disabled:opacity-50"
                >
                  {loading ? "Processing..." : "Capture & Recognize"}
                </button>
                <button
                  onClick={stopCamera}
                  className="px-5 py-2.5 bg-danger text-white text-[14px] font-medium rounded-xl hover:opacity-90 transition-all duration-200"
                >
                  Stop Camera
                </button>
              </>
            )}

            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={loading}
              className="px-5 py-2.5 border border-divider text-[14px] font-medium rounded-xl hover:bg-background-secondary transition-colors duration-200 disabled:opacity-50"
            >
              Upload Photo
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              onChange={handleFileUpload}
              className="hidden"
            />
          </div>
        </div>

        {/* Results Section */}
        <div className="bg-card border border-divider rounded-2xl p-7 shadow-[var(--shadow-sm)]">
          <h2 className="text-[17px] font-semibold tracking-[-0.01em] mb-5">Results</h2>

          {loading && (
            <div className="flex items-center justify-center h-40">
              <div className="text-foreground-secondary text-[14px]">
                Recognizing faces...
              </div>
            </div>
          )}

          {!loading && !result && (
            <div className="py-12 text-center">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.2" className="mx-auto mb-3 text-foreground-secondary opacity-40">
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              <p className="text-foreground-secondary text-[14px]">
                Capture a photo or upload an image to see results.
              </p>
            </div>
          )}

          {result && (
            <div className="space-y-4">
              <div className="flex items-center gap-4 p-4 bg-background-secondary rounded-xl">
                <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="text-primary">
                    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                    <circle cx="9" cy="7" r="4" />
                  </svg>
                </div>
                <div>
                  <p className="text-[15px] font-semibold text-foreground">
                    {result.total_faces} face{result.total_faces !== 1 ? "s" : ""}{" "}
                    detected
                  </p>
                  <p className="text-[13px] text-foreground-secondary">
                    {result.attendance_marked.length} attendance{" "}
                    {result.attendance_marked.length !== 1 ? "records" : "record"}{" "}
                    marked
                  </p>
                </div>
              </div>

              <div className="space-y-2">
                {result.recognized.map((name, i) => {
                  const isUnknown = name === "UNKNOWN";
                  const isNoMembers = name === "NO_REGISTERED_MEMBERS";
                  const isRecognized = !isUnknown && !isNoMembers;

                  return (
                    <div
                      key={i}
                      className={`flex items-center gap-3.5 p-3.5 rounded-xl border ${
                        isUnknown
                          ? "bg-warning-light border-warning/20"
                          : isNoMembers
                          ? "bg-danger-light border-danger/20"
                          : "bg-success-light border-success/20"
                      }`}
                    >
                      <div
                        className={`w-9 h-9 rounded-full flex items-center justify-center text-[13px] font-semibold ${
                          isUnknown
                            ? "bg-warning/15 text-warning"
                            : isNoMembers
                            ? "bg-danger/15 text-danger"
                            : "bg-success/15 text-success"
                        }`}
                      >
                        {isUnknown ? "?" : isNoMembers ? "!" : name.charAt(0).toUpperCase()}
                      </div>
                      <div>
                        <p className="text-[14px] font-medium text-foreground">
                          {isUnknown
                            ? "Unknown Person"
                            : isNoMembers
                            ? "No Members Registered"
                            : name}
                        </p>
                        <p className="text-[12px] text-foreground-secondary">
                          {isUnknown
                            ? "Face not recognized"
                            : isNoMembers
                            ? "Register members first"
                            : "Attendance marked"}
                        </p>
                      </div>
                      {isRecognized && (
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="ml-auto text-success">
                          <polyline points="20 6 9 17 4 12" />
                        </svg>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
