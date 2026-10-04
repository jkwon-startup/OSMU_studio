import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

export type Colors = { bg: string; accent: string; text: string; muted: string };
export type SceneProps = {
  template: "kinetic_full" | "bullet_card" | "data_bars" | "endcard";
  props: Record<string, any>;
  colors?: Partial<Colors>;
  durationInFrames?: number;
};

const DEFAULT_COLORS: Colors = { bg: "#0F172A", accent: "#F59E0B", text: "#FFFFFF", muted: "#94A3B8" };
const FONT = "'Pretendard', 'Noto Sans KR', 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif";

export const defaultSceneProps: SceneProps = {
  template: "kinetic_full",
  props: { text: "하루 30분, 진짜 될까요?" },
  colors: DEFAULT_COLORS,
  durationInFrames: 90,
};

const useEnter = (delay = 0) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: frame - delay, fps, config: { damping: 14, stiffness: 120 } });
  return { opacity: interpolate(s, [0, 1], [0, 1]), translateY: interpolate(s, [0, 1], [60, 0]) };
};

const Frame: React.FC<{ colors: Colors; children: React.ReactNode }> = ({ colors, children }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const fadeOut = interpolate(frame, [durationInFrames - 8, durationInFrames], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ backgroundColor: colors.bg, fontFamily: FONT, color: colors.text, opacity: fadeOut }}>
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 18, background: colors.accent }} />
      {children}
    </AbsoluteFill>
  );
};

const KineticFull: React.FC<{ text: string; colors: Colors }> = ({ text, colors }) => {
  const words = text.split(" ");
  return (
    <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", padding: 90 }}>
      <div style={{ fontSize: text.length > 10 ? 96 : 120, fontWeight: 800, lineHeight: 1.25, textAlign: "center", wordBreak: "keep-all" }}>
        {words.map((w, i) => (
          <Word key={i} delay={i * 4} colors={colors} highlight={/\d/.test(w)}>{w}{" "}</Word>
        ))}
      </div>
    </div>
  );
};

const Word: React.FC<{ delay: number; colors: Colors; highlight: boolean; children: React.ReactNode }> = ({ delay, colors, highlight, children }) => {
  const { opacity, translateY } = useEnter(delay);
  return <span style={{ display: "inline-block", opacity, transform: `translateY(${translateY}px)`, color: highlight ? colors.accent : colors.text }}>{children}</span>;
};

const BulletCard: React.FC<{ title: string; items: string[]; colors: Colors }> = ({ title, items, colors }) => {
  const t = useEnter(0);
  return (
    <div style={{ position: "absolute", inset: 0, padding: "360px 100px" }}>
      <div style={{ fontSize: 84, fontWeight: 800, lineHeight: 1.2, opacity: t.opacity, transform: `translateY(${t.translateY}px)`, wordBreak: "keep-all" }}>{title}</div>
      <div style={{ marginTop: 70, display: "flex", flexDirection: "column", gap: 44 }}>
        {items.slice(0, 3).map((it, i) => (
          <Bullet key={i} delay={12 + i * 10} colors={colors}>{it}</Bullet>
        ))}
      </div>
    </div>
  );
};

const Bullet: React.FC<{ delay: number; colors: Colors; children: React.ReactNode }> = ({ delay, colors, children }) => {
  const { opacity, translateY } = useEnter(delay);
  return (
    <div style={{ display: "flex", gap: 28, alignItems: "flex-start", opacity, transform: `translateY(${translateY}px)` }}>
      <div style={{ width: 30, height: 30, borderRadius: 15, background: colors.accent, marginTop: 18, flexShrink: 0 }} />
      <div style={{ fontSize: 58, lineHeight: 1.35, wordBreak: "keep-all" }}>{children}</div>
    </div>
  );
};

const DataBars: React.FC<{ title: string; bars: { label: string; value: number; unit?: string }[]; colors: Colors }> = ({ title, bars, colors }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const max = Math.max(1, ...bars.map((b) => b.value));
  return (
    <div style={{ position: "absolute", inset: 0, padding: "380px 100px" }}>
      <div style={{ fontSize: 80, fontWeight: 800, marginBottom: 60 }}>{title}</div>
      {bars.slice(0, 4).map((b, i) => {
        const p = spring({ frame: frame - 10 - i * 8, fps, config: { damping: 18 } });
        return (
          <div key={i} style={{ marginBottom: 58 }}>
            <div style={{ fontSize: 50, color: colors.muted, marginBottom: 14 }}>{b.label}  <span style={{ color: colors.text, fontWeight: 700 }}>{Math.round(b.value * p)}{b.unit ?? ""}</span></div>
            <div style={{ height: 40, width: `${(b.value / max) * 100 * p}%`, background: colors.accent, borderRadius: 8 }} />
          </div>
        );
      })}
    </div>
  );
};

const EndCard: React.FC<{ title: string; sub?: string; colors: Colors }> = ({ title, sub, colors }) => {
  const t = useEnter(0);
  const s = useEnter(10);
  return (
    <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: 90, textAlign: "center" }}>
      <div style={{ fontSize: 104, fontWeight: 800, lineHeight: 1.2, opacity: t.opacity, transform: `translateY(${t.translateY}px)`, wordBreak: "keep-all" }}>{title}</div>
      {sub && <div style={{ marginTop: 40, fontSize: 48, color: colors.muted, opacity: s.opacity, transform: `translateY(${s.translateY}px)` }}>{sub}</div>}
    </div>
  );
};

export const Scene: React.FC<SceneProps> = ({ template, props, colors }) => {
  const c: Colors = { ...DEFAULT_COLORS, ...(colors ?? {}) };
  return (
    <Frame colors={c}>
      {template === "kinetic_full" && <KineticFull text={String(props.text ?? "")} colors={c} />}
      {template === "bullet_card" && <BulletCard title={String(props.title ?? "")} items={(props.items ?? []).map(String)} colors={c} />}
      {template === "data_bars" && <DataBars title={String(props.title ?? "")} bars={props.bars ?? []} colors={c} />}
      {template === "endcard" && <EndCard title={String(props.title ?? "")} sub={props.sub} colors={c} />}
    </Frame>
  );
};
