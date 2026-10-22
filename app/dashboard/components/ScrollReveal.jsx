"use client";
// Scroll-reveal for cards: each `.main .card` fades and rises into place the
// first time it enters the viewport, with a short stagger. Cards that render
// later (after data loads) are picked up by a MutationObserver. Nothing hides
// for people who prefer reduced motion, or when printing (see globals.css).
import { useEffect } from "react";
import { usePathname } from "next/navigation";

export default function ScrollReveal() {
  const path = usePathname();

  useEffect(() => {
    const main = document.querySelector(".main");
    if (!main || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    let fired = false;
    const io = new IntersectionObserver((entries) => {
      fired = true;
      for (const e of entries) {
        if (e.isIntersecting) {
          e.target.classList.add("in");
          io.unobserve(e.target);
        }
      }
    }, { rootMargin: "0px 0px -6% 0px", threshold: 0.06 });

    let n = 0;
    const tag = () => {
      main.querySelectorAll(".card:not([data-reveal])").forEach((el) => {
        el.setAttribute("data-reveal", "");
        el.style.setProperty("--reveal-delay", `${(n++ % 6) * 70}ms`);
        el.classList.add("reveal");
        io.observe(el);
      });
    };
    tag();
    const mo = new MutationObserver(tag);
    mo.observe(main, { childList: true, subtree: true });
    // Safety net: if the observer never reports (e.g. the page isn't being
    // drawn), show everything rather than leave content invisible.
    const fallback = setTimeout(() => {
      if (!fired) main.querySelectorAll(".card.reveal").forEach((el) => el.classList.add("in"));
    }, 1500);
    return () => { clearTimeout(fallback); mo.disconnect(); io.disconnect(); };
  }, [path]);

  return null;
}
