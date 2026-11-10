"use client";

import Image from "next/image";

interface AnimeMascotProps {
  stage?: string;
  isProcessing?: boolean;
  className?: string;
}

export default function AnimeMascot({
  stage = "Processing",
  isProcessing = true,
  className = "",
}: AnimeMascotProps) {
  return (
    <div
      className={`relative flex items-center justify-center ${className}`}
      data-processing={isProcessing ? "true" : "false"}
      role="img"
      aria-label={`Clip Finder AI dancing mascot - ${stage}`}
    >
      {/* Background radial ambient glow - purple and cyan */}
      <div
        className={`pointer-events-none absolute h-36 w-36 rounded-full bg-gradient-to-tr from-purple-600/25 via-cyan-500/20 to-emerald-400/20 blur-2xl transition-all duration-1000 ${
          isProcessing ? "animate-pulse opacity-100 scale-110" : "opacity-40 scale-95"
        }`}
        aria-hidden="true"
      />

      {/* Outer energy ring pulse */}
      <div
        className={`pointer-events-none absolute h-40 w-40 rounded-full border border-purple-500/20 transition-all duration-700 ${
          isProcessing ? "scale-105 opacity-80" : "scale-100 opacity-20"
        }`}
        aria-hidden="true"
      />

      {/* Dancing Anime Mascot Animation */}
      <div className="relative z-10 flex h-[160px] w-[160px] items-center justify-center motion-safe:transition-transform">
        <Image
          src="/images/anime-mascot-dance.gif"
          alt=""
          aria-hidden="true"
          width={150}
          height={150}
          unoptimized
          priority
          className="cf-mascot-motion select-none object-contain drop-shadow-[0_10px_25px_rgba(168,85,247,0.35)]"
        />
        <Image
          src="/images/anime-mascot-still.png"
          alt=""
          aria-hidden="true"
          width={150}
          height={150}
          priority
          className="cf-mascot-still hidden select-none object-contain drop-shadow-[0_10px_25px_rgba(168,85,247,0.35)]"
        />
      </div>

      {/* Floating Sparkle / Music Note Particle Accents */}
      {isProcessing && (
        <>
          <span
            className="pointer-events-none absolute -top-1 -right-2 text-xs text-cyan-400 opacity-80 animate-bounce motion-reduce:hidden"
            style={{ animationDuration: "2.4s" }}
            aria-hidden="true"
          >
            ✦
          </span>
          <span
            className="pointer-events-none absolute top-4 -left-3 text-xs text-purple-400 opacity-75 animate-bounce motion-reduce:hidden"
            style={{ animationDuration: "3.1s", animationDelay: "0.5s" }}
            aria-hidden="true"
          >
            ♪
          </span>
          <span
            className="pointer-events-none absolute bottom-4 -right-2 text-[10px] text-emerald-400 opacity-70 animate-bounce motion-reduce:hidden"
            style={{ animationDuration: "2.8s", animationDelay: "1.2s" }}
            aria-hidden="true"
          >
            ✧
          </span>
        </>
      )}
    </div>
  );
}
