"use client";
import React, { useState } from "react";
import { DashboardShell } from "@/components/dashboard/shell";
import { PATIENT_NAV } from "@/lib/constants";
import { Mic, MicOff, Send, Bot, User, Sparkles, CheckCircle2, Calendar, Clock, AlertCircle, Volume2 } from "lucide-react";
import { mockDoctors } from "@/lib/mock-data";

interface Message {
  id: string;
  sender: "ai" | "user";
  text: string;
  timestamp: string;
  actionCard?: {
    type: "slot_picker" | "booking_confirmation" | "pre_visit_form";
    data: any;
  };
}

export default function PatientAssistantPage() {
  const [isListening, setIsListening] = useState(false);
  const [inputText, setInputText] = useState("");
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "1",
      sender: "ai",
      text: "Hello Michael! I'm your AI Healthcare Assistant. How can I help you today? You can say things like 'Book an appointment with a cardiologist next Tuesday' or ask questions about symptoms.",
      timestamp: "Just now",
    },
  ]);
  const [step, setStep] = useState<number>(0);

  const handleSend = (textToSend?: string) => {
    const text = textToSend || inputText;
    if (!text.trim()) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      sender: "user",
      text,
      timestamp: "Just now",
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputText("");

    // Simulate AI response based on step
    setTimeout(() => {
      if (step === 0) {
        const aiMsg: Message = {
          id: (Date.now() + 1).toString(),
          sender: "ai",
          text: "I found Dr. Robert Chen (Cardiology) at City General Hospital. Here are the top available time slots for next Tuesday:",
          timestamp: "Just now",
          actionCard: {
            type: "slot_picker",
            data: {
              doctor: "Dr. Robert Chen",
              specialty: "Cardiology",
              slots: [
                { id: "s1", time: "Tue, Oct 24 • 09:30 AM", fee: "$150" },
                { id: "s2", time: "Tue, Oct 24 • 02:00 PM", fee: "$150" },
                { id: "s3", time: "Tue, Oct 24 • 04:30 PM", fee: "$150" },
              ],
            },
          },
        };
        setMessages((prev) => [...prev, aiMsg]);
        setStep(1);
      } else if (step === 1) {
        const aiMsg: Message = {
          id: (Date.now() + 1).toString(),
          sender: "ai",
          text: "Great choice! To ensure Dr. Chen is well-prepared, could you briefly describe the main reason for your visit and if you are currently experiencing any chest discomfort or palpitations?",
          timestamp: "Just now",
        };
        setMessages((prev) => [...prev, aiMsg]);
        setStep(2);
      } else {
        const aiMsg: Message = {
          id: (Date.now() + 1).toString(),
          sender: "ai",
          text: "Thank you! I have booked your appointment and updated Dr. Chen's clinical pre-visit notes. A confirmation SMS and calendar invite have been dispatched.",
          timestamp: "Just now",
          actionCard: {
            type: "booking_confirmation",
            data: {
              bookingId: "APT-88219",
              doctor: "Dr. Robert Chen, MD",
              specialty: "Cardiology",
              hospital: "City General Hospital - Suite 402",
              dateTime: "Tuesday, Oct 24, 2026 at 09:30 AM",
              status: "Confirmed",
            },
          },
        };
        setMessages((prev) => [...prev, aiMsg]);
        setStep(0);
      }
    }, 1000);
  };

  const handleSelectSlot = (slotTime: string) => {
    handleSend(`I would like the slot on ${slotTime}`);
  };

  const toggleListening = () => {
    if (!isListening) {
      setIsListening(true);
      setTimeout(() => {
        setIsListening(false);
        handleSend("I need to see a cardiologist next week for a routine checkup.");
      }, 3000);
    } else {
      setIsListening(false);
    }
  };

  return (
    <DashboardShell
      navItems={PATIENT_NAV}
      role="patient"
      sidebarTitle="Patient Portal"
      sidebarSubtitle="AI Voice Assistant"
    >
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-6">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold tracking-tight text-foreground">AI Voice & Booking Assistant</h1>
              <span className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-600 border border-emerald-500/20">
                <Sparkles className="h-3 w-3" /> Live Agent
              </span>
            </div>
            <p className="text-sm text-muted-foreground mt-1">
              Speak or chat naturally to schedule visits, ask clinical preparation questions, or update pre-visit records.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={toggleListening}
              className={`inline-flex items-center gap-2 px-5 py-2.5 rounded-xl font-semibold text-sm transition-all shadow-md ${
                isListening
                  ? "bg-rose-500 text-white animate-pulse shadow-rose-500/30"
                  : "bg-primary text-primary-foreground hover:opacity-90 shadow-primary/20"
              }`}
            >
              {isListening ? (
                <>
                  <MicOff className="h-4 w-4" />
                  Listening (Speak now)...
                </>
              ) : (
                <>
                  <Mic className="h-4 w-4" />
                  Start Voice Mode
                </>
              )}
            </button>
          </div>
        </div>

        {/* Audio Waveform Animation during listening */}
        {isListening && (
          <div className="rounded-2xl border border-rose-500/30 bg-rose-500/5 p-6 flex flex-col items-center justify-center gap-4 animate-in fade-in">
            <div className="flex items-center gap-1.5 h-12">
              {[40, 75, 95, 60, 30, 85, 100, 70, 45, 90, 60, 30].map((h, i) => (
                <div
                  key={i}
                  className="w-1.5 bg-rose-500 rounded-full animate-pulse"
                  style={{
                    height: `${h}%`,
                    animationDelay: `${i * 80}ms`,
                    animationDuration: "800ms",
                  }}
                />
              ))}
            </div>
            <p className="text-xs font-semibold text-rose-600">
              Capturing audio stream • Deepgram Nova-3 Active
            </p>
          </div>
        )}

        {/* Chat Stream Window */}
        <div className="rounded-2xl border border-border bg-card shadow-sm p-6 flex flex-col h-[520px]">
          <div className="flex-1 overflow-y-auto space-y-6 pr-2">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex gap-3.5 ${
                  msg.sender === "user" ? "flex-row-reverse" : "flex-row"
                }`}
              >
                <div
                  className={`h-9 w-9 rounded-xl flex items-center justify-center shrink-0 ${
                    msg.sender === "user"
                      ? "bg-primary text-primary-foreground font-semibold text-xs"
                      : "bg-emerald-500/15 text-emerald-600 border border-emerald-500/30"
                  }`}
                >
                  {msg.sender === "user" ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
                </div>

                <div
                  className={`space-y-3 max-w-[80%] ${
                    msg.sender === "user" ? "items-end" : "items-start"
                  }`}
                >
                  <div
                    className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                      msg.sender === "user"
                        ? "bg-primary text-primary-foreground rounded-tr-none"
                        : "bg-muted text-foreground rounded-tl-none border border-border"
                    }`}
                  >
                    {msg.text}
                  </div>

                  {/* Dynamic Action Cards */}
                  {msg.actionCard?.type === "slot_picker" && (
                    <div className="rounded-2xl border border-border bg-background p-4 shadow-sm space-y-3">
                      <div className="text-xs font-bold text-muted-foreground uppercase tracking-wider">
                        Available Consultation Slots
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                        {msg.actionCard.data.slots.map((s: any) => (
                          <button
                            key={s.id}
                            onClick={() => handleSelectSlot(s.time)}
                            className="p-3 rounded-xl border border-border bg-card hover:border-emerald-500 hover:bg-emerald-500/5 transition-all text-left flex flex-col justify-between gap-1 group"
                          >
                            <span className="text-xs font-semibold text-foreground group-hover:text-emerald-600">
                              {s.time}
                            </span>
                            <span className="text-[11px] text-muted-foreground font-medium">
                              Fee: {s.fee}
                            </span>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {msg.actionCard?.type === "booking_confirmation" && (
                    <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/5 p-5 shadow-sm space-y-4">
                      <div className="flex items-center gap-2 text-emerald-600 font-bold text-sm">
                        <CheckCircle2 className="h-5 w-5" />
                        Appointment Successfully Confirmed!
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                        <div className="p-3 rounded-xl bg-card border border-border">
                          <span className="text-muted-foreground block mb-1">Booking Ref</span>
                          <span className="font-mono font-bold text-foreground">
                            {msg.actionCard.data.bookingId}
                          </span>
                        </div>
                        <div className="p-3 rounded-xl bg-card border border-border">
                          <span className="text-muted-foreground block mb-1">Doctor</span>
                          <span className="font-bold text-foreground">
                            {msg.actionCard.data.doctor}
                          </span>
                        </div>
                        <div className="p-3 rounded-xl bg-card border border-border sm:col-span-2">
                          <span className="text-muted-foreground block mb-1">Time & Venue</span>
                          <span className="font-semibold text-foreground">
                            {msg.actionCard.data.dateTime} • {msg.actionCard.data.hospital}
                          </span>
                        </div>
                      </div>
                    </div>
                  )}

                  <span className="text-[10px] text-muted-foreground block px-1">
                    {msg.timestamp}
                  </span>
                </div>
              </div>
            ))}
          </div>

          {/* Chat Input Footer */}
          <div className="mt-4 pt-4 border-t border-border flex items-center gap-3">
            <input
              type="text"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSend()}
              placeholder="Ask anything or request a booking (e.g. 'Book cardiology slot next week')..."
              className="flex-1 rounded-xl border border-border bg-background px-4 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
            />
            <button
              onClick={() => handleSend()}
              className="inline-flex items-center justify-center h-10 w-10 rounded-xl bg-primary text-primary-foreground hover:opacity-90 transition-opacity shadow"
            >
              <Send className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>
    </DashboardShell>
  );
}
