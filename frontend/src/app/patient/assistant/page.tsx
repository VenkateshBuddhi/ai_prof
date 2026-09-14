"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  Room,
  RoomEvent,
  Track,
  type Participant,
  type RemoteTrack,
  type TranscriptionSegment,
} from "livekit-client";
import { Bot, Loader2, Mic, MicOff, PhoneCall, PhoneOff, User } from "lucide-react";

import { DashboardShell } from "@/components/dashboard/shell";
import { PATIENT_NAV } from "@/lib/constants";
import { apiPost } from "@/lib/api";

type Status = "idle" | "connecting" | "live" | "ended" | "error";
type Line = { id: string; who: "agent" | "you"; text: string; final: boolean };

interface TokenResponse {
  url: string;
  token: string;
  room: string;
}

export default function PatientAssistantPage() {
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState("");
  const [micOn, setMicOn] = useState(true);
  const [lines, setLines] = useState<Line[]>([]);

  const roomRef = useRef<Room | null>(null);
  const audioRef = useRef<HTMLDivElement | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [lines]);

  // clean up on unmount
  useEffect(() => () => void roomRef.current?.disconnect(), []);

  const upsert = (seg: TranscriptionSegment, who: "agent" | "you") =>
    setLines((prev) => {
      const idx = prev.findIndex((l) => l.id === seg.id);
      const line: Line = { id: seg.id, who, text: seg.text, final: seg.final };
      if (idx >= 0) {
        const copy = [...prev];
        copy[idx] = line;
        return copy;
      }
      return [...prev, line];
    });

  const connect = useCallback(async () => {
    setStatus("connecting");
    setError("");
    setLines([]);
    try {
      const { url, token } = await apiPost<TokenResponse>("/api/voice/token", { name: "Patient" });
      const room = new Room();
      roomRef.current = room;

      room.on(RoomEvent.TrackSubscribed, (track: RemoteTrack) => {
        if (track.kind === Track.Kind.Audio) {
          const el = track.attach();
          el.autoplay = true;
          audioRef.current?.appendChild(el);
        }
      });
      room.on(
        RoomEvent.TranscriptionReceived,
        (segments: TranscriptionSegment[], participant?: Participant) => {
          const who = participant && !participant.isLocal ? "agent" : "you";
          segments.forEach((s) => upsert(s, who));
        }
      );
      room.on(RoomEvent.Disconnected, () => setStatus("ended"));

      await room.connect(url, token);
      await room.localParticipant.setMicrophoneEnabled(true);
      setMicOn(true);
      setStatus("live");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to connect");
      setStatus("error");
    }
  }, []);

  const disconnect = useCallback(async () => {
    await roomRef.current?.disconnect();
    roomRef.current = null;
    setStatus("ended");
  }, []);

  const toggleMic = useCallback(async () => {
    const lp = roomRef.current?.localParticipant;
    if (!lp) return;
    const next = !micOn;
    await lp.setMicrophoneEnabled(next);
    setMicOn(next);
  }, [micOn]);

  const isLive = status === "live";
  const statusPill = {
    idle: ["bg-gray-100 text-gray-600", "Not connected"],
    connecting: ["bg-amber-100 text-amber-700", "Connecting…"],
    live: ["bg-emerald-100 text-emerald-700", "● Live"],
    ended: ["bg-gray-100 text-gray-600", "Call ended"],
    error: ["bg-red-100 text-red-700", "Error"],
  }[status];

  return (
    <DashboardShell
      navItems={PATIENT_NAV}
      sidebarTitle="AI.Prof"
      sidebarSubtitle="Patient"
      pageTitle="AI Assistant"
      pageSubtitle="Talk to the scheduling assistant by voice, right in your browser"
    >
      <div className="mx-auto max-w-2xl">
        {/* Status + controls */}
        <div className="mb-6 flex items-center justify-between rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-blue-500 to-cyan-400">
              <Bot className="h-5 w-5 text-white" />
            </div>
            <div>
              <p className="text-sm font-semibold">Healthcare Assistant</p>
              <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${statusPill[0]}`}>
                {statusPill[1]}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {isLive && (
              <button
                onClick={toggleMic}
                className={`flex h-11 w-11 items-center justify-center rounded-full transition ${
                  micOn ? "bg-blue-100 text-blue-700 hover:bg-blue-200" : "bg-gray-200 text-gray-500"
                }`}
                title={micOn ? "Mute" : "Unmute"}
              >
                {micOn ? <Mic className="h-5 w-5" /> : <MicOff className="h-5 w-5" />}
              </button>
            )}
            {isLive ? (
              <button
                onClick={disconnect}
                className="flex items-center gap-2 rounded-full bg-red-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-red-700"
              >
                <PhoneOff className="h-4 w-4" /> End
              </button>
            ) : (
              <button
                onClick={connect}
                disabled={status === "connecting"}
                className="flex items-center gap-2 rounded-full bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60"
              >
                {status === "connecting" ? <Loader2 className="h-4 w-4 animate-spin" /> : <PhoneCall className="h-4 w-4" />}
                {status === "connecting" ? "Connecting" : status === "ended" ? "Call again" : "Start call"}
              </button>
            )}
          </div>
        </div>

        {error && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
        )}

        {/* Live transcript */}
        <div
          ref={scrollRef}
          className="h-[420px] space-y-3 overflow-y-auto rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-5"
        >
          {lines.length === 0 && (
            <div className="flex h-full flex-col items-center justify-center text-center text-sm text-[hsl(var(--muted-foreground))]">
              <Bot className="mb-3 h-10 w-10 opacity-40" />
              {status === "idle" && "Press “Start call” and allow microphone access, then just talk — e.g. “I’d like to book a cardiologist.”"}
              {status === "connecting" && "Connecting to the assistant…"}
              {status === "live" && "Listening… say something to begin."}
              {status === "ended" && "Call ended. Press “Call again” to start over."}
              {status === "error" && "Couldn’t connect. Check the backend + LiveKit worker are running."}
            </div>
          )}
          {lines.map((l) => (
            <div key={l.id} className={`flex gap-2 ${l.who === "you" ? "flex-row-reverse" : ""}`}>
              <div className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full ${l.who === "you" ? "bg-blue-600" : "bg-gradient-to-br from-blue-500 to-cyan-400"}`}>
                {l.who === "you" ? <User className="h-4 w-4 text-white" /> : <Bot className="h-4 w-4 text-white" />}
              </div>
              <div className={`max-w-[80%] rounded-2xl px-4 py-2 text-sm ${
                l.who === "you" ? "bg-blue-600 text-white" : "bg-[hsl(var(--muted))] text-[hsl(var(--foreground))]"
              } ${l.final ? "" : "opacity-70"}`}>
                {l.text}
              </div>
            </div>
          ))}
        </div>

        {/* agent audio elements are attached here */}
        <div ref={audioRef} className="hidden" />
      </div>
    </DashboardShell>
  );
}
