"use client";

export const dynamic = "force-dynamic";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  signInWithEmailAndPassword,
  signInWithPopup,
  GoogleAuthProvider,
  OAuthProvider,
  PhoneAuthProvider,
  RecaptchaVerifier,
} from "firebase/auth";
import { auth } from "@/lib/firebase";
import { api } from "@/lib/api-client";
import { useAuthStore } from "@/store/auth-store";

export default function LoginPage() {
  const router = useRouter();
  const { setUser, setProfile } = useAuthStore();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<"email" | "phone">("email");
  const [phone, setPhone] = useState("");
  const [otp, setOtp] = useState("");
  const [otpSent, setOtpSent] = useState(false);
  const [verificationId, setVerificationId] = useState("");

  async function handleProfile(firebaseUser: any) {
    setUser(firebaseUser);
    try {
      const profile = await api.get<{ tenantId: string; role: string; permissions: string[] }>("/auth/me");
      setProfile(profile);
    } catch {}
    router.push("/");
  }

  async function handleEmailLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const cred = await signInWithEmailAndPassword(auth, email, password);
      await handleProfile(cred.user);
    } catch (err: any) {
      setError(err.message || "Login failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleGoogleLogin() {
    setLoading(true);
    setError("");
    try {
      const provider = new GoogleAuthProvider();
      const cred = await signInWithPopup(auth, provider);
      await handleProfile(cred.user);
    } catch (err: any) {
      setError(err.message || "Google login failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleMicrosoftLogin() {
    setLoading(true);
    setError("");
    try {
      const provider = new OAuthProvider("microsoft.com");
      const cred = await signInWithPopup(auth, provider);
      await handleProfile(cred.user);
    } catch (err: any) {
      setError(err.message || "Microsoft login failed");
    } finally {
      setLoading(false);
    }
  }

  // Dev mode: bypass auth
  async function handleDevLogin() {
    setLoading(true);
    setProfile({ tenantId: "dev_tenant_001", role: "TENANT_ADMIN", permissions: ["*"] });
    router.push("/");
    setLoading(false);
  }

  return (
    <div className="min-h-screen bg-[#030712] flex items-center justify-center p-4 relative overflow-hidden">
      {/* Animated gradient background */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute -top-40 -left-40 w-96 h-96 bg-violet-600/20 rounded-full blur-3xl animate-pulse" />
        <div className="absolute top-1/2 -right-40 w-96 h-96 bg-cyan-500/20 rounded-full blur-3xl animate-pulse delay-1000" />
        <div className="absolute -bottom-40 left-1/2 w-96 h-96 bg-indigo-500/15 rounded-full blur-3xl animate-pulse delay-500" />
        {/* Grid background */}
        <div
          className="absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage: `linear-gradient(rgba(255,255,255,.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.1) 1px, transparent 1px)`,
            backgroundSize: "50px 50px",
          }}
        />
      </div>

      <div className="relative z-10 w-full max-w-md">
        {/* Logo + Branding */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-violet-600 to-indigo-600 mb-4 shadow-2xl shadow-violet-500/30">
            <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
              <path d="M16 2L28 8V16C28 22.627 22.627 28 16 28C9.373 28 4 22.627 4 16V8L16 2Z" fill="rgba(255,255,255,0.15)" stroke="white" strokeWidth="1.5" />
              <path d="M12 16L15 19L20 13" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <h1 className="text-3xl font-bold text-white tracking-tight">
            Anti<span className="text-transparent bg-clip-text bg-gradient-to-r from-violet-400 to-cyan-400">Gravity</span>
          </h1>
          <p className="text-slate-400 mt-1 text-sm">Autonomous Enterprise AI Platform</p>
        </div>

        {/* Login Card */}
        <div className="bg-slate-900/80 backdrop-blur-xl border border-slate-700/50 rounded-2xl p-8 shadow-2xl">
          {/* SSO Buttons */}
          <div className="space-y-3 mb-6">
            <button
              onClick={handleGoogleLogin}
              disabled={loading}
              className="w-full flex items-center justify-center gap-3 px-4 py-3 bg-slate-800 hover:bg-slate-700 border border-slate-600/50 rounded-xl text-white text-sm font-medium transition-all duration-200 hover:border-slate-500 disabled:opacity-50"
            >
              <svg width="18" height="18" viewBox="0 0 24 24">
                <path fill="#4285F4" d="M23.745 12.27c0-.79-.07-1.54-.19-2.27h-11.3v4.51h6.47c-.29 1.48-1.14 2.73-2.4 3.58v3h3.86c2.26-2.09 3.56-5.17 3.56-8.82z" />
                <path fill="#34A853" d="M12.255 24c3.24 0 5.95-1.08 7.93-2.91l-3.86-3c-1.08.72-2.45 1.16-4.07 1.16-3.13 0-5.78-2.11-6.73-4.96h-3.98v3.09C3.515 21.3 7.615 24 12.255 24z" />
                <path fill="#FBBC05" d="M5.525 14.29c-.25-.72-.38-1.49-.38-2.29s.14-1.57.38-2.29V6.62h-3.98a11.86 11.86 0 0 0 0 10.76l3.98-3.09z" />
                <path fill="#EA4335" d="M12.255 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C18.205 1.19 15.495 0 12.255 0c-4.64 0-8.74 2.7-10.71 6.62l3.98 3.09c.95-2.85 3.6-4.96 6.73-4.96z" />
              </svg>
              Continue with Google
            </button>
            <button
              onClick={handleMicrosoftLogin}
              disabled={loading}
              className="w-full flex items-center justify-center gap-3 px-4 py-3 bg-slate-800 hover:bg-slate-700 border border-slate-600/50 rounded-xl text-white text-sm font-medium transition-all duration-200 hover:border-slate-500 disabled:opacity-50"
            >
              <svg width="18" height="18" viewBox="0 0 24 24">
                <path fill="#f25022" d="M1 1h10v10H1z" />
                <path fill="#00a4ef" d="M13 1h10v10H13z" />
                <path fill="#7fba00" d="M1 13h10v10H1z" />
                <path fill="#ffb900" d="M13 13h10v10H13z" />
              </svg>
              Continue with Microsoft
            </button>
          </div>

          {/* Divider */}
          <div className="relative mb-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-slate-700" />
            </div>
            <div className="relative flex justify-center text-xs text-slate-500 bg-slate-900 px-2">or continue with</div>
          </div>

          {/* Tab switcher: Email / Phone */}
          <div className="flex rounded-lg bg-slate-800/50 p-1 mb-6 gap-1">
            {(["email", "phone"] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`flex-1 py-2 rounded-md text-sm font-medium transition-all capitalize ${
                  activeTab === tab
                    ? "bg-violet-600 text-white shadow-sm"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                {tab === "email" ? "Email" : "Phone OTP"}
              </button>
            ))}
          </div>

          {activeTab === "email" && (
            <form onSubmit={handleEmailLogin} className="space-y-4">
              <div>
                <label className="block text-sm text-slate-400 mb-1.5">Email Address</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@company.com"
                  required
                  className="w-full px-4 py-3 bg-slate-800 border border-slate-600/50 rounded-xl text-white placeholder-slate-500 text-sm focus:outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500/30 transition-all"
                />
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-1.5">Password</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  className="w-full px-4 py-3 bg-slate-800 border border-slate-600/50 rounded-xl text-white placeholder-slate-500 text-sm focus:outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500/30 transition-all"
                />
              </div>
              {error && (
                <div className="text-red-400 text-sm bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-3">
                  {error}
                </div>
              )}
              <button
                type="submit"
                disabled={loading}
                className="w-full py-3 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white rounded-xl font-medium text-sm transition-all duration-200 shadow-lg shadow-violet-500/25 disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {loading ? "Signing in..." : "Sign In"}
              </button>
            </form>
          )}

          {activeTab === "phone" && (
            <div className="space-y-4">
              {!otpSent ? (
                <>
                  <div>
                    <label className="block text-sm text-slate-400 mb-1.5">Mobile Number (India)</label>
                    <div className="flex gap-2">
                      <div className="flex items-center px-3 bg-slate-800 border border-slate-600/50 rounded-xl text-slate-400 text-sm">
                        🇮🇳 +91
                      </div>
                      <input
                        type="tel"
                        value={phone}
                        onChange={(e) => setPhone(e.target.value)}
                        placeholder="9876543210"
                        className="flex-1 px-4 py-3 bg-slate-800 border border-slate-600/50 rounded-xl text-white placeholder-slate-500 text-sm focus:outline-none focus:border-violet-500 transition-all"
                      />
                    </div>
                  </div>
                  <div id="recaptcha-container" />
                  <button
                    onClick={() => setOtpSent(true)}
                    disabled={loading}
                    className="w-full py-3 bg-gradient-to-r from-violet-600 to-indigo-600 text-white rounded-xl font-medium text-sm disabled:opacity-60"
                  >
                    Send OTP
                  </button>
                </>
              ) : (
                <>
                  <div>
                    <label className="block text-sm text-slate-400 mb-1.5">Enter OTP</label>
                    <input
                      type="text"
                      value={otp}
                      onChange={(e) => setOtp(e.target.value)}
                      placeholder="Enter 6-digit OTP"
                      maxLength={6}
                      className="w-full px-4 py-3 bg-slate-800 border border-slate-600/50 rounded-xl text-white text-center text-xl tracking-[0.5em] placeholder-slate-500 focus:outline-none focus:border-violet-500 transition-all"
                    />
                  </div>
                  <button
                    onClick={() => {}}
                    disabled={loading || otp.length !== 6}
                    className="w-full py-3 bg-gradient-to-r from-violet-600 to-indigo-600 text-white rounded-xl font-medium text-sm disabled:opacity-60"
                  >
                    {loading ? "Verifying..." : "Verify OTP"}
                  </button>
                </>
              )}
            </div>
          )}

          {/* Dev bypass */}
          {process.env.NODE_ENV === "development" && (
            <button
              onClick={handleDevLogin}
              className="mt-4 w-full py-2 text-xs text-slate-500 hover:text-slate-300 border border-slate-700 rounded-lg transition-colors"
            >
              🔧 Dev Mode Login (skip auth)
            </button>
          )}
        </div>

        <p className="text-center text-xs text-slate-600 mt-6">
          AntiGravity v2.0 · India-Ready · No Supabase · NERVE Architecture
        </p>
      </div>
    </div>
  );
}
