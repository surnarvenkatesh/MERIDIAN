import { useState } from "react";
import { Compass } from "lucide-react";
import { login, register } from "../lib/api";

interface Props {
  onAuthenticated: (token: string, email: string) => void;
}

export default function AuthScreen({ onAuthenticated }: Props) {
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const result = mode === "login" ? await login(email, password) : await register(email, password);
      onAuthenticated(result.token, result.email);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-screen w-full items-center justify-center bg-ink px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex items-center justify-center gap-2">
          <Compass className="h-6 w-6 text-signal-amber" strokeWidth={1.75} />
          <span className="font-display text-xl tracking-tight text-parchment">Meridian</span>
        </div>

        <div className="rounded-lg border border-ink-line bg-ink-panel p-6 shadow-panel">
          <h1 className="mb-1 font-display text-[18px] text-parchment">
            {mode === "login" ? "Welcome back" : "Create your account"}
          </h1>
          <p className="mb-5 text-[12.5px] text-parchment-faint">
            {mode === "login"
              ? "Log in to see your research history."
              : "Sign up to keep your research sessions private to you."}
          </p>

          <form onSubmit={submit} className="flex flex-col gap-3">
            <div>
              <label className="mb-1 block text-[11.5px] text-parchment-faint">Email</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
                className="w-full rounded-md border border-ink-line bg-ink px-3 py-2 text-[13.5px] text-parchment outline-none focus:border-signal-amberDim"
              />
            </div>
            <div>
              <label className="mb-1 block text-[11.5px] text-parchment-faint">Password</label>
              <input
                type="password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                className="w-full rounded-md border border-ink-line bg-ink px-3 py-2 text-[13.5px] text-parchment outline-none focus:border-signal-amberDim"
              />
              {mode === "signup" && (
                <p className="mt-1 text-[11px] text-parchment-faint">At least 8 characters.</p>
              )}
            </div>

            {error && (
              <div className="rounded-md border border-signal-clayDim/50 bg-signal-clayDim/10 px-3 py-2 text-[12px] text-signal-clay">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="mt-1 flex items-center justify-center rounded-md bg-signal-amber py-2 text-[13px] font-medium text-ink transition-colors hover:bg-[#eeb156] disabled:opacity-50"
            >
              {loading ? "Please wait…" : mode === "login" ? "Log in" : "Sign up"}
            </button>
          </form>

          <button
            onClick={() => {
              setMode(mode === "login" ? "signup" : "login");
              setError(null);
            }}
            className="mt-4 w-full text-center text-[12px] text-parchment-faint hover:text-parchment-dim"
          >
            {mode === "login" ? "Don't have an account? Sign up" : "Already have an account? Log in"}
          </button>
        </div>
      </div>
    </div>
  );
}
