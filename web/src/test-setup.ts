import '@testing-library/jest-dom/vitest'

// jsdom lacks IntersectionObserver (scroll-triggered motion) and matchMedia. Elements report as
// visible at once, and tests run with "reduce motion" on, so counters show final values
// immediately (the same path real users with reduced motion get).
class ImmediateIntersectionObserver {
  private cb: IntersectionObserverCallback
  constructor(cb: IntersectionObserverCallback) { this.cb = cb }
  observe(target: Element) {
    this.cb([{ isIntersecting: true, target, intersectionRatio: 1 } as IntersectionObserverEntry], this as unknown as IntersectionObserver)
  }
  unobserve() {}
  disconnect() {}
  takeRecords() { return [] }
}
globalThis.IntersectionObserver ??= ImmediateIntersectionObserver as unknown as typeof IntersectionObserver
window.matchMedia ??= ((query: string) => ({
  matches: query.includes('prefers-reduced-motion'), media: query, onchange: null,
  addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {}, dispatchEvent() { return false },
})) as typeof window.matchMedia
