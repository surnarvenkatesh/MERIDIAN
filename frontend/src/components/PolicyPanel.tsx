import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { TrendingUp } from "lucide-react";
import type { PolicySnapshot } from "../lib/types";
import { ACTION_META } from "../lib/actionMeta";

export default function PolicyPanel({ policy }: { policy: PolicySnapshot | null }) {
  if (!policy) {
    return (
      <div className="rounded-lg border border-ink-line bg-ink-panel px-4 py-4">
        <span className="text-[12px] text-parchment-faint">Loading policy telemetry…</span>
      </div>
    );
  }

  const chartData = policy.reward_history.map((r, i) => ({ episode: i + 1, reward: r }));
  const totalActions = Object.values(policy.action_distribution).reduce((a, b) => a + b, 0) || 1;

  return (
    <div className="rounded-lg border border-ink-line bg-ink-panel px-4 py-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <TrendingUp className="h-3.5 w-3.5 text-signal-teal" strokeWidth={1.75} />
          <span className="text-[11px] font-medium uppercase tracking-wide text-parchment-faint">RL Policy</span>
        </div>
        <span className="font-mono text-[10.5px] text-parchment-faint">{policy.episodes_trained} episodes</span>
      </div>

      <div className="h-[92px] w-full">
        {chartData.length > 1 ? (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 4, right: 0, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id="rewardFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#5FBEA5" stopOpacity={0.4} />
                  <stop offset="100%" stopColor="#5FBEA5" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="episode" hide />
              <YAxis hide domain={["dataMin - 0.1", "dataMax + 0.1"]} />
              <Tooltip
                contentStyle={{
                  background: "#1C2733",
                  border: "1px solid rgba(236,231,221,0.16)",
                  borderRadius: 6,
                  fontSize: 11,
                  fontFamily: "JetBrains Mono, monospace",
                }}
                labelFormatter={(l) => `episode ${l}`}
                formatter={(v: number) => [v.toFixed(3), "reward"]}
              />
              <Area type="monotone" dataKey="reward" stroke="#5FBEA5" strokeWidth={1.75} fill="url(#rewardFill)" />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex h-full items-center justify-center text-[11.5px] text-parchment-faint">
            Reward curve appears after a few sessions.
          </div>
        )}
      </div>

      <div className="mt-3 flex items-center justify-between font-mono text-[10.5px] text-parchment-faint">
        <span>avg reward</span>
        <span className="text-signal-teal">{policy.running_avg_reward.toFixed(3)}</span>
      </div>

      <div className="mt-3 border-t border-ink-line pt-3">
        <span className="text-[10.5px] font-medium uppercase tracking-wide text-parchment-faint">
          Action preference
        </span>
        <div className="mt-2 flex flex-col gap-1.5">
          {policy.action_names.map((name) => {
            const count = policy.action_distribution[name] ?? 0;
            const pct = (count / totalActions) * 100;
            const meta = ACTION_META[name as keyof typeof ACTION_META];
            return (
              <div key={name} className="flex items-center gap-2">
                <span className="w-[92px] shrink-0 truncate text-[10.5px] text-parchment-faint">
                  {meta?.label.split(" ")[0] ?? name}
                </span>
                <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-ink">
                  <div className={`h-full ${meta?.dotClass ?? "bg-signal-amber"}`} style={{ width: `${pct}%` }} />
                </div>
                <span className="w-7 shrink-0 text-right font-mono text-[10px] text-parchment-faint">{count}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
