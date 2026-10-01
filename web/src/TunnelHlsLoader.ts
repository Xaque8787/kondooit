import type {
  Loader,
  LoaderCallbacks,
  LoaderConfiguration,
  LoaderContext,
  LoaderStats,
  HlsConfig,
} from "hls.js";
import { apiFetch } from "./api";

function createStats(): LoaderStats {
  return {
    aborted: false,
    loaded: 0,
    retry: 0,
    total: 0,
    chunkCount: 0,
    bwEstimate: 0,
    loading: { start: 0, first: 0, end: 0 },
    parsing: { start: 0, end: 0 },
    buffering: { start: 0, first: 0, end: 0 },
  };
}

export class TunnelHlsLoader implements Loader<LoaderContext> {
  private abortController: AbortController | null = null;
  public context!: LoaderContext;
  public stats: LoaderStats = createStats();

  constructor(_config: HlsConfig) {}

  load(
    context: LoaderContext,
    _config: LoaderConfiguration,
    callbacks: LoaderCallbacks<LoaderContext>,
  ): void {
    this.context = context;
    this.stats = createStats();
    this.stats.loading.start = performance.now();

    const ac = new AbortController();
    this.abortController = ac;

    apiFetch(context.url, { signal: ac.signal })
      .then(async (res) => {
        if (ac.signal.aborted) return;
        this.stats.loading.first = performance.now();

        if (!res.ok) {
          callbacks.onError(
            { code: res.status, text: res.statusText },
            context,
            res,
            this.stats,
          );
          return;
        }

        const data =
          context.responseType === "arraybuffer"
            ? await res.arrayBuffer()
            : await res.text();

        const len = typeof data === "string" ? data.length : data.byteLength;
        this.stats.loaded = len;
        this.stats.total = len;
        this.stats.loading.end = performance.now();

        callbacks.onSuccess(
          { url: context.url, data },
          this.stats,
          context,
          res,
        );
      })
      .catch((err) => {
        if (ac.signal.aborted) return;
        this.stats.loading.end = performance.now();
        callbacks.onError(
          { code: 0, text: err?.message || "Network error" },
          context,
          null,
          this.stats,
        );
      });
  }

  abort(): void {
    this.abortController?.abort();
    this.stats.aborted = true;
  }

  destroy(): void {
    this.abort();
  }
}
