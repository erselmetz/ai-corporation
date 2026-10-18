type State = "loading" | "ready" | "empty" | "sign-in" | "denied" | "failed" | "unknown";
type Result = { state: State; message: string; source: string; values?: Record<string, string> };
type Payload = Record<string, unknown>;

function record(value: unknown): value is Payload {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function formatBytes(bytes: unknown): string {
  if (typeof bytes !== "number" || !Number.isFinite(bytes) || bytes < 0) return "UNKNOWN";
  return `${(bytes / (1024 ** 3)).toFixed(1)} GiB`;
}

export function summarizeHardwareProfile(body: Payload): Result {
  const fields = [body.cpu, body.gpu, body.memory, body.disk];
  if (!fields.every(record)) return { state: "unknown", message: "Hardware observations have an unsupported shape.", source: "/api/system/hardware-profile" };
  const [cpu, gpu, memory, disk] = fields as Payload[];
  const describe = (label: string, observation: Payload, value: string) => {
    const checked = typeof observation.observed_at === "string" ? observation.observed_at : "timestamp unknown";
    if (observation.state !== "observed") {
      const reason = typeof observation.reason === "string" ? observation.reason : "No supported observation is available.";
      return `${label}: UNKNOWN â€” ${reason}; checked ${checked}`;
    }
    const source = typeof observation.source === "string" ? observation.source : "source unknown";
    return `${label}: ${value}; source ${source}; observed ${checked}`;
  };
  const cpuValue = record(cpu.value)
    ? `${typeof cpu.value.name === "string" ? cpu.value.name : "CPU name unknown"}${typeof cpu.value.logical_processors === "number" ? `, ${cpu.value.logical_processors} logical processors` : ""}`
    : "CPU details unknown";
  const gpuValue = Array.isArray(gpu.value)
    ? gpu.value.length ? gpu.value.map(item => record(item) && typeof item.name === "string" ? item.name : "GPU name unknown").join("; ") : "No hardware GPU adapter reported"
    : "GPU details unknown";
  const memoryValue = record(memory.value)
    ? `${formatBytes(memory.value.total_bytes)} total, ${formatBytes(memory.value.available_bytes)} currently available`
    : "Memory totals unknown";
  const diskValue = record(disk.value)
    ? `${formatBytes(disk.value.free_bytes)} free of ${formatBytes(disk.value.total_bytes)} at the ${disk.value.destination === "custom" ? "configured" : "default"} Ollama model destination`
    : "Disk capacity unknown";
  const recommendation = record(body.recommendation) ? body.recommendation : {};
  const modelClass = typeof recommendation.ollama_model_class === "string" ? recommendation.ollama_model_class : "UNKNOWN";
  const warning = typeof recommendation.cpu_warning === "string" ? recommendation.cpu_warning : "CPU/GPU execution mode is unknown.";
  const basis = typeof recommendation.basis === "string" ? recommendation.basis : "No recommendation basis was returned.";
  const fitClaim = typeof recommendation.fit_claim === "string" ? recommendation.fit_claim : "A recommendation does not guarantee fit or performance.";
  const observed = fields.filter(field => field.state === "observed").length;
  return {
    state: observed ? "ready" : "unknown",
    message: `Suggested Ollama class: ${modelClass}. ${warning} ${basis} ${fitClaim} This check does not install or download anything.`,
    source: typeof body.observed_at === "string" ? `Local snapshot ${body.observed_at}` : "/api/system/hardware-profile",
    values: {
      CPU: describe("CPU", cpu, cpuValue),
      GPU: describe("GPU", gpu, gpuValue),
      Memory: describe("Memory", memory, memoryValue),
      Disk: describe("Disk", disk, diskValue),
    },
  };
}
