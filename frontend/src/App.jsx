import { useEffect, useRef, useState } from "react";

const API_BASE = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");

function EmptyState({ title, text }) {
  return (
    <div className="empty-state soft-glass" role="status">
      <p className="empty-state__title">{title}</p>
      <p className="empty-state__text">{text}</p>
    </div>
  );
}

function formatCount(value, singular, plural) {
  return `${value} ${value === 1 ? singular : plural}`;
}

function interactiveProps() {
  return {
    className: "soft-glass",
  };
}

export default function App() {
  const [detections, setDetections] = useState([]);
  const [synced, setSynced] = useState([]);
  const [waypointPreview, setWaypointPreview] = useState("");
  const [activeDetection, setActiveDetection] = useState(null);

  const pollRef = useRef(null);

  useEffect(() => {
    async function poll() {
      try {
        const [detectionRes, syncedRes, previewRes] = await Promise.all([
          fetch(`${API_BASE}/api/detections`),
          fetch(`${API_BASE}/api/synced`),
          fetch(`${API_BASE}/api/waypoints/preview`),
        ]);

        const detectionData = detectionRes.ok ? await detectionRes.json() : [];
        const syncedData = syncedRes.ok ? await syncedRes.json() : [];
        const previewData = previewRes.ok ? await previewRes.json() : { content: "" };

        setDetections(Array.isArray(detectionData) ? detectionData : []);
        setSynced(Array.isArray(syncedData) ? syncedData : []);
        setWaypointPreview(previewData.content || "");
      } catch {
        setDetections([]);
        setSynced([]);
        setWaypointPreview("");
      }
    }

    let cancelled = false;

    async function boot() {
      try {
        await fetch(`${API_BASE}/api/session/reset`, { method: "DELETE" });
      } catch {
        // Ignore reset failures and continue polling current state.
      }

      if (cancelled) {
        return;
      }

      await poll();
      pollRef.current = window.setInterval(poll, 3500);
    }

    boot();
    return () => {
      cancelled = true;
      window.clearInterval(pollRef.current);
    };
  }, []);

  useEffect(() => {
    function handleKeydown(event) {
      if (event.key === "Escape") {
        setActiveDetection(null);
      }
    }

    window.addEventListener("keydown", handleKeydown);
    return () => window.removeEventListener("keydown", handleKeydown);
  }, []);

  return (
    <div className="page-shell">
      <div className="mesh mesh--one" aria-hidden="true" />
      <div className="mesh mesh--two" aria-hidden="true" />

      <header className="hero">
        <div className="hero__brand-block">
          <img className="hero__logo" src="/dridha-transparent.png" alt="Dridha" />
        </div>
        <div className="hero__stats">
          <article {...interactiveProps()} className="hero-stat glass-interactive">
            <span className="hero-stat__label">Detections</span>
            <strong className="hero-stat__value">{detections.length}</strong>
          </article>
          <article {...interactiveProps()} className="hero-stat glass-interactive">
            <span className="hero-stat__label">Synced</span>
            <strong className="hero-stat__value">{synced.length}</strong>
          </article>
          <article {...interactiveProps()} className="hero-stat glass-interactive">
            <span className="hero-stat__label">Mission</span>
            <strong className="hero-stat__value">{waypointPreview ? "Ready" : "Standby"}</strong>
          </article>
        </div>
      </header>

      <main className="page-grid">
        <section {...interactiveProps()} className="panel glass-interactive" aria-labelledby="detections-title">
          <div className="panel__head">
            <div>
              <p className="panel__eyebrow">Detections</p>
              <h2 id="detections-title">{formatCount(detections.length, "result", "results")}</h2>
            </div>
          </div>

          {detections.length ? (
            <div className="photo-carousel" role="list" aria-label="Detected weed images">
              {[...detections].reverse().map((item) => (
                <article
                  key={item.id}
                  {...interactiveProps()}
                  className="photo-card photo-card--carousel soft-glass photo-card--clickable"
                  role="listitem"
                  onClick={() => setActiveDetection(item)}
                >
                  <img
                    src={`${API_BASE}/api/detections/${item.id}/image`}
                    alt={`Detection result for ${item.name}`}
                    className="photo-card__image"
                  />
                  <div className="photo-card__body">
                    <div className="photo-card__topline">
                      <p className="photo-card__title">{formatCount(item.count, "weed", "weeds")} detected</p>
                      <p className="photo-card__time">{item.time}</p>
                    </div>
                    <p className="photo-card__name">{item.name}</p>
                    <p className="photo-card__coords">
                      {item.lat}, {item.lon}
                    </p>
                    <p className="photo-card__confidence">Confidence {(item.confidence * 100).toFixed(0)}%</p>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <EmptyState title="No detections yet" text="New boxed weed detections will surface here from the current session only." />
          )}
        </section>

        <section {...interactiveProps()} className="panel glass-interactive" aria-labelledby="synced-title">
          <div className="panel__head">
            <div>
              <p className="panel__eyebrow">Synced Photos</p>
              <h2 id="synced-title">{formatCount(synced.length, "photo", "photos")}</h2>
            </div>
          </div>

          {synced.length ? (
            <div className="photo-carousel" role="list" aria-label="Synced photos">
              {[...synced].reverse().map((item) => (
                <article key={item.id} {...interactiveProps()} className="photo-card photo-card--carousel photo-card--synced soft-glass" role="listitem">
                  <img
                    src={`${API_BASE}/api/synced/${item.id}/image`}
                    alt={`Synced image ${item.name}`}
                    className="photo-card__image"
                  />
                  <div className="photo-card__body">
                    <div className="photo-card__topline">
                      <p className="photo-card__title">Synced photo</p>
                      <p className="photo-card__time">{item.time}</p>
                    </div>
                    <p className="photo-card__name">{item.name}</p>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <EmptyState title="No synced photos yet" text="Incoming WeedEye images from this fresh session will appear here automatically." />
          )}
        </section>

        <section {...interactiveProps()} className="panel soft-glass" aria-labelledby="waypoints-title">
          <div className="panel__head panel__head--spread">
            <div>
              <p className="panel__eyebrow">Waypoints</p>
              <h2 id="waypoints-title">Mission file ready</h2>
            </div>
            <a {...interactiveProps()} className="button-primary soft-glass" href={`${API_BASE}/api/waypoints/download`}>
              Download .waypoints
            </a>
          </div>

          {waypointPreview ? (
            <pre className="waypoint-preview">{waypointPreview}</pre>
          ) : (
            <EmptyState title="No mission file yet" text="Only new verified detections from this run will populate the mission file." />
          )}
        </section>
      </main>

      {activeDetection ? (
        <div className="lightbox" role="dialog" aria-modal="true" aria-label="Detection image preview" onClick={() => setActiveDetection(null)}>
          <div className="lightbox__panel soft-glass" onClick={(event) => event.stopPropagation()}>
            <button className="lightbox__close" type="button" onClick={() => setActiveDetection(null)}>
              Close
            </button>
            <img
              className="lightbox__image"
              src={`${API_BASE}/api/detections/${activeDetection.id}/image`}
              alt={`Expanded detection result for ${activeDetection.name}`}
            />
            <div className="lightbox__meta">
              <p className="lightbox__title">{activeDetection.name}</p>
              <p>{formatCount(activeDetection.count, "weed", "weeds")} detected</p>
              <p>
                {activeDetection.lat}, {activeDetection.lon}
              </p>
              <p>Confidence {(activeDetection.confidence * 100).toFixed(0)}%</p>
              <p>{activeDetection.time}</p>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
