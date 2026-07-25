import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  CircleMarker,
  MapContainer,
  TileLayer,
  ZoomControl,
  useMap,
} from "react-leaflet";

import "leaflet/dist/leaflet.css";
import "./App.css";

/* ============================================================
   CONFIGURATION
============================================================ */

const API_BASE =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

const NAGOYA_CENTER = [35.17, 136.9];

const STATION = {
  lat: 35.1708336,
  lon: 136.881256,
};

const MONTHS = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

const DAY_TYPES = [
  {
    value: 1,
    label: "Weekday",
    short: "WD",
  },
  {
    value: 2,
    label: "Holiday",
    short: "HD",
  },
];

const TIME_PERIODS = [
  {
    value: 1,
    label: "Daytime",
    short: "DAY",
  },
  {
    value: 2,
    label: "Nighttime",
    short: "NIGHT",
  },
];

/* ============================================================
   UTILITY FUNCTIONS
============================================================ */

function formatNumber(value) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }

  return Number(value).toLocaleString();
}

function formatPercent(value) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }

  const rounded = Number(value).toFixed(1);

  return `${rounded > 0 ? "+" : ""}${rounded}%`;
}

function clamp(value, min = 0, max = 1) {
  return Math.min(Math.max(value, min), max);
}

function haversineKm(lon1, lat1, lon2, lat2) {
  const toRad = (degree) => (degree * Math.PI) / 180;

  const dLon = toRad(lon2 - lon1);
  const dLat = toRad(lat2 - lat1);

  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) *
      Math.cos(toRad(lat2)) *
      Math.sin(dLon / 2) ** 2;

  return 6371 * 2 * Math.asin(Math.sqrt(a));
}

/**
 * Dynamic gradient based on normalized value.
 *
 * 0 = central / closest
 * 1 = peripheral / farthest
 */
function distanceColor(value) {
  const t = clamp(value);

  const stops = [
    {
      position: 0,
      color: [255, 107, 74],
    },
    {
      position: 0.5,
      color: [255, 180, 84],
    },
    {
      position: 1,
      color: [45, 212, 191],
    },
  ];

  let lower = stops[0];
  let upper = stops[stops.length - 1];

  for (let i = 0; i < stops.length - 1; i++) {
    if (
      t >= stops[i].position &&
      t <= stops[i + 1].position
    ) {
      lower = stops[i];
      upper = stops[i + 1];
      break;
    }
  }

  const localT =
    (t - lower.position) /
    (upper.position - lower.position || 1);

  const rgb = lower.color.map((channel, index) =>
    Math.round(
      channel +
        (upper.color[index] - channel) * localT
    )
  );

  return `rgb(${rgb.join(", ")})`;
}

function getPredictionStatus(prediction) {
  if (!prediction) {
    return {
      label: "No prediction",
      className: "neutral",
    };
  }

  const change = prediction.vs_historical_average_pct;

  if (change > 15) {
    return {
      label: "High activity",
      className: "high",
    };
  }

  if (change > 5) {
    return {
      label: "Above average",
      className: "positive",
    };
  }

  if (change < -15) {
    return {
      label: "Low activity",
      className: "low",
    };
  }

  if (change < -5) {
    return {
      label: "Below average",
      className: "negative",
    };
  }

  return {
    label: "Normal activity",
    className: "neutral",
  };
}

/* ============================================================
   API CLIENT
============================================================ */

const api = {
  async request(endpoint, options = {}) {
    const response = await fetch(
      `${API_BASE}${endpoint}`,
      {
        ...options,
        headers: {
          Accept: "application/json",
          ...options.headers,
        },
      }
    );

    if (!response.ok) {
      throw new Error(
        `API request failed: ${response.status}`
      );
    }

    return response.json();
  },

  getAreas(signal) {
    return this.request("/areas", {
      signal,
    });
  },

  getPrediction(areaId, params, signal) {
    const query = new URLSearchParams({
      month: params.month,
      dayflag: params.dayflag,
      timezone: params.timezone,
    });

    return this.request(
      `/prediction/${areaId}?${query.toString()}`,
      {
        signal,
      }
    );
  },

  getFlow(areaId, signal) {
    return this.request(`/flow/${areaId}`, {
      signal,
    });
  },
};

/* ============================================================
   CUSTOM HOOKS
============================================================ */

function useAreas() {
  const [areas, setAreas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadAreas = useCallback(async () => {
    const controller = new AbortController();

    try {
      setLoading(true);
      setError(null);

      const data = await api.getAreas(
        controller.signal
      );

      setAreas(data.areas || []);
    } catch (err) {
      if (err.name !== "AbortError") {
        setError(err);
      }
    } finally {
      setLoading(false);
    }

    return () => controller.abort();
  }, []);

  useEffect(() => {
    loadAreas();
  }, [loadAreas]);

  return {
    areas,
    loading,
    error,
    reload: loadAreas,
  };
}

function useAreaAnalytics(
  selectedArea,
  month,
  dayflag,
  timezone
) {
  const [prediction, setPrediction] = useState(null);
  const [flow, setFlow] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!selectedArea) {
      setPrediction(null);
      setFlow(null);
      return;
    }

    const controller = new AbortController();

    async function loadAnalytics() {
      try {
        setLoading(true);
        setError(null);

        const [predictionData, flowData] =
          await Promise.all([
            api.getPrediction(
              selectedArea.area_id,
              {
                month,
                dayflag,
                timezone,
              },
              controller.signal
            ),

            api.getFlow(
              selectedArea.area_id,
              controller.signal
            ),
          ]);

        setPrediction(predictionData);
        setFlow(flowData);
      } catch (err) {
        if (err.name !== "AbortError") {
          setError(err);
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    loadAnalytics();

    return () => controller.abort();
  }, [
    selectedArea,
    month,
    dayflag,
    timezone,
  ]);

  return {
    prediction,
    flow,
    loading,
    error,
  };
}

/* ============================================================
   MAP HELPERS
============================================================ */

function FlyToSelectedArea({ area }) {
  const map = useMap();

  useEffect(() => {
    if (!area) return;

    map.flyTo(
      [area.lat, area.lon],
      14,
      {
        duration: 0.8,
      }
    );
  }, [area, map]);

  return null;
}

/* ============================================================
   SPARKLINE
============================================================ */

function Sparkline({
  data = [],
  height = 90,
}) {
  const [hoverIndex, setHoverIndex] =
    useState(null);

  const chart = useMemo(() => {
    if (!data.length) return null;

    const width = 500;
    const padding = 12;

    const values = data.map(
      (item) => item.value
    );

    const min = Math.min(...values);
    const max = Math.max(...values);

    const range = max - min || 1;

    const step =
      data.length === 1
        ? 0
        : (width - padding * 2) /
          (data.length - 1);

    const coordinates = data.map(
      (item, index) => {
        const x = padding + index * step;

        const y =
          height -
          padding -
          ((item.value - min) / range) *
            (height - padding * 2);

        return {
          ...item,
          x,
          y,
        };
      }
    );

    const linePath = coordinates
      .map(
        (point, index) =>
          `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`
      )
      .join(" ");

    const areaPath = `
      ${linePath}
      L ${coordinates.at(-1).x} ${height}
      L ${coordinates[0].x} ${height}
      Z
    `;

    return {
      width,
      min,
      max,
      coordinates,
      linePath,
      areaPath,
    };
  }, [data, height]);

  if (!chart) {
    return (
      <div className="chart-empty">
        No historical data
      </div>
    );
  }

  const hovered =
    hoverIndex !== null
      ? chart.coordinates[hoverIndex]
      : null;

  function handleMouseMove(event) {
    const rect =
      event.currentTarget.getBoundingClientRect();

    const x =
      ((event.clientX - rect.left) /
        rect.width) *
      chart.width;

    let closestIndex = 0;
    let closestDistance = Infinity;

    chart.coordinates.forEach(
      (point, index) => {
        const distance = Math.abs(
          point.x - x
        );

        if (distance < closestDistance) {
          closestDistance = distance;
          closestIndex = index;
        }
      }
    );

    setHoverIndex(closestIndex);
  }

  return (
    <div className="sparkline-wrapper">
      <div className="chart-header">
        <span>
          Peak {formatNumber(chart.max)}
        </span>

        <span>
          Low {formatNumber(chart.min)}
        </span>
      </div>

      <div className="chart-container">
        <svg
          viewBox={`0 0 ${chart.width} ${height}`}
          preserveAspectRatio="none"
          onMouseMove={handleMouseMove}
          onMouseLeave={() =>
            setHoverIndex(null)
          }
        >
          <defs>
            <linearGradient
              id="mobilityGradient"
              x1="0"
              y1="0"
              x2="0"
              y2="1"
            >
              <stop
                offset="0%"
                stopColor="#2dd4bf"
                stopOpacity="0.35"
              />

              <stop
                offset="100%"
                stopColor="#2dd4bf"
                stopOpacity="0"
              />
            </linearGradient>
          </defs>

          <line
            x1="0"
            x2={chart.width}
            y1={height / 2}
            y2={height / 2}
            stroke="#26303b"
            strokeWidth="1"
          />

          <path
            d={chart.areaPath}
            fill="url(#mobilityGradient)"
          />

          <path
            d={chart.linePath}
            fill="none"
            stroke="#2dd4bf"
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {hovered && (
            <>
              <line
                x1={hovered.x}
                x2={hovered.x}
                y1="0"
                y2={height}
                stroke="#2dd4bf"
                strokeDasharray="3 4"
              />

              <circle
                cx={hovered.x}
                cy={hovered.y}
                r="5"
                fill="#ffffff"
                stroke="#2dd4bf"
                strokeWidth="3"
              />
            </>
          )}
        </svg>

        {hovered && (
          <div
            className="chart-tooltip"
            style={{
              left: `${(hovered.x / chart.width) * 100}%`,
            }}
          >
            <strong>
              {MONTHS[hovered.month - 1]}
            </strong>

            <span>
              {formatNumber(hovered.value)}
              {" people"}
            </span>
          </div>
        )}
      </div>

      <div className="chart-axis">
        {data.map((item, index) => (
          <span key={index}>
            {index % 2 === 0
              ? MONTHS[item.month - 1]
              : ""}
          </span>
        ))}
      </div>
    </div>
  );
}

/* ============================================================
   LANDING PAGE
============================================================ */

function Landing({
  onEnter,
  previewAreas,
}) {
  useEffect(() => {
    function handleKeyDown(event) {
      if (event.key === "Enter") {
        onEnter();
      }
    }

    window.addEventListener(
      "keydown",
      handleKeyDown
    );

    return () => {
      window.removeEventListener(
        "keydown",
        handleKeyDown
      );
    };
  }, [onEnter]);

  return (
    <main className="landing">
      <div className="landing-layout">
        <section className="landing-content">
          <div className="landing-eyebrow">
            REAL MLIT PEOPLE-FLOW DATA · 2019
          </div>

          <h1 className="landing-title">
            Nagoya
            <br />
            Mobility
            <br />
            Forecast
          </h1>

          <p className="landing-sub">
            An interactive mobility intelligence
            console for analysing population
            movement across Nagoya's mesh areas.
          </p>

          <div className="landing-stats">
            <Stat
              value={previewAreas.length}
              label="mesh areas"
            />

            <Stat
              value="35,065"
              label="observations"
            />

            <Stat
              value="0.987"
              label="model R²"
            />

            <Stat
              value="16"
              label="wards covered"
            />
          </div>

          <button
            className="landing-cta"
            onClick={onEnter}
          >
            Enter the console
            <span>→</span>
          </button>

          <div className="landing-hint">
            Press Enter to continue
          </div>
        </section>

        <section className="landing-preview">
          <div className="preview-label">
            <span className="preview-dot" />
            LIVE MESH DATA
          </div>

          <div className="preview-map">
            {previewAreas.length > 0 ? (
              <MapContainer
                center={NAGOYA_CENTER}
                zoom={11}
                zoomControl={false}
                dragging={false}
                scrollWheelZoom={false}
                doubleClickZoom={false}
                attributionControl={false}
                style={{
                  height: "100%",
                  width: "100%",
                }}
              >
                <TileLayer
                  url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
                />

                {previewAreas.map((area) => (
                  <CircleMarker
                    key={area.area_id}
                    center={[
                      area.lat,
                      area.lon,
                    ]}
                    radius={6}
                    pathOptions={{
                      color: area.color,
                      fillColor: area.color,
                      fillOpacity: 0.85,
                      weight: 0,
                    }}
                  />
                ))}
              </MapContainer>
            ) : (
              <div className="preview-loading">
                Loading mesh data...
              </div>
            )}
          </div>
        </section>
      </div>
    </main>
  );
}

/* ============================================================
   SMALL COMPONENTS
============================================================ */

function Stat({ value, label }) {
  return (
    <div className="landing-stat">
      <div className="landing-stat-number">
        {value}
      </div>

      <div className="landing-stat-label">
        {label}
      </div>
    </div>
  );
}

function ToggleGroup({
  options,
  value,
  onChange,
}) {
  return (
    <div className="toggle-group">
      {options.map((option) => (
        <button
          key={option.value}
          className={
            value === option.value
              ? "toggle active"
              : "toggle"
          }
          onClick={() =>
            onChange(option.value)
          }
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="loading-state">
      <div className="skeleton skeleton-large" />
      <div className="skeleton skeleton-medium" />
      <div className="skeleton skeleton-small" />
    </div>
  );
}

function ErrorMessage({ error }) {
  if (!error) return null;

  return (
    <div className="error-message">
      <strong>
        Unable to load analytics
      </strong>

      <span>
        {error.message ||
          "Something went wrong."}
      </span>
    </div>
  );
}

/* ============================================================
   ANALYTICS PANEL
============================================================ */

function AnalyticsPanel({
  selectedArea,
  prediction,
  flow,
  loading,
  error,
  dayflag,
  setDayflag,
  timezone,
  setTimezone,
}) {
  const sparkPoints = useMemo(() => {
    if (!flow?.history?.length) {
      return [];
    }

    const grouped = {};

    flow.history.forEach((row) => {
      if (!grouped[row.month]) {
        grouped[row.month] = [];
      }

      grouped[row.month].push(
        row.population
      );
    });

    return Object.entries(grouped)
      .sort(
        ([monthA], [monthB]) =>
          Number(monthA) - Number(monthB)
      )
      .map(([month, values]) => ({
        month: Number(month),

        value:
          values.reduce(
            (sum, value) => sum + value,
            0
          ) / values.length,
      }));
  }, [flow]);

  const status =
    getPredictionStatus(prediction);

  if (!selectedArea) {
    return (
      <aside className="panel panel-empty">
        <div className="empty-panel-content">
          <span className="empty-icon">
            ◎
          </span>

          <h3>
            Select a mesh area
          </h3>

          <p>
            Choose a location on the map
            to inspect its mobility forecast.
          </p>
        </div>
      </aside>
    );
  }

  return (
    <aside className="panel panel-open">
      <div className="panel-header">
        <div className="panel-eyebrow">
          SELECTED AREA
        </div>

        <h2>
          {selectedArea.ward}
        </h2>

        <div className="panel-meta">
          MESH {selectedArea.area_id}
        </div>
      </div>

      <div className="control-section">
        <div className="control-label">
          DAY TYPE
        </div>

        <ToggleGroup
          options={DAY_TYPES}
          value={dayflag}
          onChange={setDayflag}
        />
      </div>

      <div className="control-section">
        <div className="control-label">
          TIME PERIOD
        </div>

        <ToggleGroup
          options={TIME_PERIODS}
          value={timezone}
          onChange={setTimezone}
        />
      </div>

      {loading && <LoadingSkeleton />}

      <ErrorMessage error={error} />

      {prediction && !loading && (
        <section className="prediction-section">
          <div className="prediction-status">
            <span
              className={`status-pill ${status.className}`}
            >
              {status.label}
            </span>
          </div>

          <div className="predicted-number">
            {formatNumber(
              prediction.predicted_people
            )}
          </div>

          <div className="predicted-label">
            predicted people · current model
          </div>

          {prediction.historical_range && (
            <HistoricalRange
              prediction={prediction}
            />
          )}

          {prediction.vs_historical_average_pct !==
            null && (
            <div
              className={
                prediction.vs_historical_average_pct >=
                0
                  ? "delta up"
                  : "delta down"
              }
            >
              {prediction.vs_historical_average_pct >=
              0
                ? "▲"
                : "▼"}{" "}
              {formatPercent(
                prediction.vs_historical_average_pct
              )}{" "}
              vs yearly average
            </div>
          )}
        </section>
      )}

      {sparkPoints.length > 0 && (
        <section className="trend-section">
          <div className="section-title">
            2019 MONTHLY TREND
          </div>

          <Sparkline data={sparkPoints} />
        </section>
      )}
    </aside>
  );
}

function HistoricalRange({
  prediction,
}) {
  const range =
    prediction.historical_range;

  const percentage = clamp(
    (prediction.predicted_people -
      range.min) /
      (range.max - range.min || 1)
  );

  return (
    <div className="historical-range">
      <div className="range-values">
        <span>
          {formatNumber(range.min)}
        </span>

        <span>
          {formatNumber(range.max)}
        </span>
      </div>

      <div className="range-track">
        <div className="range-fill" />

        <div
          className="range-marker"
          style={{
            left: `${percentage * 100}%`,
          }}
        />
      </div>
    </div>
  );
}

/* ============================================================
   MONTH SCRUBBER
============================================================ */

function MonthScrubber({
  month,
  setMonth,
  selectedArea,
}) {
  return (
    <div
      className={
        selectedArea
          ? "scrubber scrubber-panel-open"
          : "scrubber"
      }
    >
      <div className="scrubber-label">
        MONTH
      </div>

      <div className="scrubber-track">
        {MONTHS.map((monthName, index) => {
          const monthValue = index + 1;

          return (
            <button
              key={monthName}
              className={
                month === monthValue
                  ? "month-tick active"
                  : "month-tick"
              }
              onClick={() =>
                setMonth(monthValue)
              }
            >
              <span className="tick-mark" />

              <span className="tick-label">
                {monthName}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

/* ============================================================
   MAIN APP
============================================================ */

function App() {
  const {
    areas,
    loading: areasLoading,
    error: areasError,
    reload: reloadAreas,
  } = useAreas();

  const [entered, setEntered] =
    useState(false);

  const [selectedArea, setSelectedArea] =
    useState(null);

  const [month, setMonth] =
    useState(10);

  const [dayflag, setDayflag] =
    useState(1);

  const [timezone, setTimezone] =
    useState(1);

  const {
    prediction,
    flow,
    loading: analyticsLoading,
    error: analyticsError,
  } = useAreaAnalytics(
    selectedArea,
    month,
    dayflag,
    timezone
  );

  const [search, setSearch] =
    useState("");

  /* ----------------------------------------------------------
     DISTANCE CALCULATIONS
  ---------------------------------------------------------- */

  const areaDistances = useMemo(() => {
    if (!areas.length) {
      return {
        distances: {},
        maxDistance: 1,
        minDistance: 0,
      };
    }

    const distances = {};

    let minDistance = Infinity;
    let maxDistance = 0;

    areas.forEach((area) => {
      const distance = haversineKm(
        area.lon,
        area.lat,
        STATION.lon,
        STATION.lat
      );

      distances[area.area_id] =
        distance;

      minDistance = Math.min(
        minDistance,
        distance
      );

      maxDistance = Math.max(
        maxDistance,
        distance
      );
    });

    return {
      distances,
      minDistance,
      maxDistance,
    };
  }, [areas]);

  /* ----------------------------------------------------------
     DYNAMIC MAP DATA
  ---------------------------------------------------------- */

  const mapAreas = useMemo(() => {
    const {
      distances,
      minDistance,
      maxDistance,
    } = areaDistances;

    return areas.map((area) => {
      const distance =
        distances[area.area_id] || 0;

      const normalized =
        (distance - minDistance) /
        (maxDistance - minDistance || 1);

      return {
        ...area,

        distance,

        normalizedDistance:
          normalized,

        color:
          distanceColor(normalized),
      };
    });
  }, [areas, areaDistances]);

  /* ----------------------------------------------------------
     SEARCH
  ---------------------------------------------------------- */

  const filteredAreas = useMemo(() => {
    const query =
      search.trim().toLowerCase();

    if (!query) {
      return mapAreas;
    }

    return mapAreas.filter((area) =>
      [
        area.ward,
        area.area_id,
      ]
        .join(" ")
        .toLowerCase()
        .includes(query)
    );
  }, [mapAreas, search]);

  /* ----------------------------------------------------------
     DASHBOARD STATS
  ---------------------------------------------------------- */

  const dashboardStats = useMemo(() => {
    if (!areas.length) {
      return {
        total: 0,
        wards: 0,
        averageDistance: 0,
      };
    }

    const wards = new Set(
      areas.map((area) => area.ward)
    );

    const distances =
      Object.values(
        areaDistances.distances
      );

    const averageDistance =
      distances.reduce(
        (sum, value) => sum + value,
        0
      ) / distances.length;

    return {
      total: areas.length,
      wards: wards.size,
      averageDistance,
    };
  }, [areas, areaDistances]);

  /* ----------------------------------------------------------
     PREVIEW
  ---------------------------------------------------------- */

  if (!entered) {
    return (
      <Landing
        onEnter={() => setEntered(true)}
        previewAreas={mapAreas}
      />
    );
  }

  return (
    <main className="app">
      {/* TOP BAR */}

      <header className="topbar">
        <div className="wordmark">
          <span className="wordmark-main">
            NAGOYA
          </span>

          <span className="wordmark-sub">
            MOBILITY FORECAST
          </span>
        </div>

        <div className="topbar-actions">
          <div className="dashboard-stats">
            <span>
              {dashboardStats.total} meshes
            </span>

            <span>
              {dashboardStats.wards} wards
            </span>

            <span>
              {dashboardStats.averageDistance.toFixed(
                1
              )}{" "}
              km avg.
            </span>
          </div>

          <div className="status">
            <span
              className={
                areasError
                  ? "status-dot offline"
                  : "status-dot online"
              }
            />

            {areasLoading
              ? "CONNECTING"
              : areasError
              ? "OFFLINE"
              : "SYSTEM ONLINE"}
          </div>
        </div>
      </header>

      {/* MAP */}

      <section className="map-stage">
        <MapContainer
          center={NAGOYA_CENTER}
          zoom={12}
          zoomControl={false}
          style={{
            height: "100%",
            width: "100%",
          }}
        >
          <ZoomControl position="bottomleft" />

          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            attribution="© CARTO © OpenStreetMap contributors"
          />

          <FlyToSelectedArea
            area={selectedArea}
          />

          {filteredAreas.map((area) => {
            const isSelected =
              selectedArea?.area_id ===
              area.area_id;

            return (
              <CircleMarker
                key={area.area_id}
                center={[
                  area.lat,
                  area.lon,
                ]}
                radius={
                  isSelected ? 14 : 8
                }
                pathOptions={{
                  color: isSelected
                    ? "#ffffff"
                    : area.color,

                  fillColor:
                    area.color,

                  fillOpacity:
                    isSelected
                      ? 1
                      : 0.78,

                  weight:
                    isSelected ? 3 : 1,
                }}
                eventHandlers={{
                  click: () =>
                    setSelectedArea(area),
                }}
              />
            );
          })}
        </MapContainer>

        {/* SEARCH */}

        <div className="map-search">
          <input
            type="search"
            value={search}
            placeholder="Search ward or mesh..."
            onChange={(event) =>
              setSearch(
                event.target.value
              )
            }
          />

          {search && (
            <button
              onClick={() => setSearch("")}
            >
              ×
            </button>
          )}
        </div>

        {/* OFFLINE */}

        {areasError && (
          <div className="offline-banner">
            <strong>
              Backend unreachable.
            </strong>

            <span>
              Make sure your FastAPI server
              is running.
            </span>

            <button
              onClick={reloadAreas}
            >
              Retry
            </button>
          </div>
        )}

        {/* EMPTY STATE */}

        {!selectedArea &&
          !areasError && (
            <div className="empty-chip">
              Select a mesh area to inspect
              its forecast
            </div>
          )}

        {/* LEGEND */}

        <div className="legend">
          <span className="legend-title">
            DISTANCE FROM STATION
          </span>

          <div className="legend-bar" />

          <div className="legend-labels">
            <span>
              {areaDistances.minDistance.toFixed(
                1
              )}{" "}
              km
            </span>

            <span>
              {areaDistances.maxDistance.toFixed(
                1
              )}{" "}
              km
            </span>
          </div>
        </div>
      </section>

      {/* ANALYTICS */}

      <AnalyticsPanel
        selectedArea={selectedArea}
        prediction={prediction}
        flow={flow}
        loading={analyticsLoading}
        error={analyticsError}
        dayflag={dayflag}
        setDayflag={setDayflag}
        timezone={timezone}
        setTimezone={setTimezone}
      />

      {/* MONTH CONTROL */}

      <MonthScrubber
        month={month}
        setMonth={setMonth}
        selectedArea={selectedArea}
      />
    </main>
  );
}

export default App;