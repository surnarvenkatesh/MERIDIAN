import { useEffect, useRef, useState } from "react";
import { Check, KeyRound, LogOut, User, X } from "lucide-react";
import { changePassword } from "../lib/api";

interface Props {
  email: string;
  onLogout: () => void;
}

export default function ProfileMenu({ email, onLogout }: Props) {
  const [open, setOpen] = useState(false);
  const [changingPassword, setChangingPassword] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false);
        setChangingPassword(false);
        setError(null);
      }
    };
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  const submitChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await changePassword(currentPassword, newPassword);
      setSuccess(true);
      setCurrentPassword("");
      setNewPassword("");
      setTimeout(() => {
        setSuccess(false);
        setChangingPassword(false);
        setOpen(false);
      }, 1500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to change password");
    }
  };

  return (
    <div className="relative" ref={menuRef}>
      <button
        onClick={() => setOpen((o) => !o)}
        title={email}
        className="flex h-7 w-7 items-center justify-center rounded-full border border-ink-line text-parchment-faint transition-colors hover:border-ink-lineStrong hover:text-parchment-dim"
      >
        <User className="h-3.5 w-3.5" />
      </button>

      {open && (
        <div className="absolute right-0 top-9 z-20 w-64 rounded-md border border-ink-lineStrong bg-ink-raised py-1 shadow-panel">
          <div className="border-b border-ink-line px-3 py-2.5">
            <p className="truncate text-[12.5px] text-parchment">{email}</p>
          </div>

          {!changingPassword ? (
            <>
              <button
                onClick={() => setChangingPassword(true)}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-[12.5px] text-parchment-dim hover:bg-ink"
              >
                <KeyRound className="h-3.5 w-3.5" /> Change password
              </button>
              <button
                onClick={onLogout}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-[12.5px] text-signal-clay hover:bg-ink"
              >
                <LogOut className="h-3.5 w-3.5" /> Log out
              </button>
            </>
          ) : (
            <form onSubmit={submitChangePassword} className="px-3 py-2.5">
              {success ? (
                <p className="flex items-center gap-1.5 text-[12.5px] text-signal-teal">
                  <Check className="h-3.5 w-3.5" /> Password updated
                </p>
              ) : (
                <>
                  <input
                    type="password"
                    required
                    placeholder="Current password"
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    className="mb-2 w-full rounded border border-ink-line bg-ink px-2 py-1.5 text-[12.5px] text-parchment outline-none focus:border-signal-amberDim"
                  />
                  <input
                    type="password"
                    required
                    minLength={8}
                    placeholder="New password (8+ chars)"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    className="mb-2 w-full rounded border border-ink-line bg-ink px-2 py-1.5 text-[12.5px] text-parchment outline-none focus:border-signal-amberDim"
                  />
                  {error && <p className="mb-2 text-[11.5px] text-signal-clay">{error}</p>}
                  <div className="flex justify-end gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        setChangingPassword(false);
                        setError(null);
                      }}
                      className="flex items-center gap-1 rounded px-2 py-1 text-[11.5px] text-parchment-faint hover:text-parchment-dim"
                    >
                      <X className="h-3 w-3" /> Cancel
                    </button>
                    <button
                      type="submit"
                      className="flex items-center gap-1 rounded bg-signal-amber px-2.5 py-1 text-[11.5px] font-medium text-ink hover:bg-[#eeb156]"
                    >
                      <Check className="h-3 w-3" /> Save
                    </button>
                  </div>
                </>
              )}
            </form>
          )}
        </div>
      )}
    </div>
  );
}
