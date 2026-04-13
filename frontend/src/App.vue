<script setup>
import { computed, onMounted, ref } from "vue";
import axios from "axios";

const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";
const HOUR_START = 6;
const HOUR_END = 24;
const HOUR_HEIGHT = 56;

const selectedDate = ref(new Date().toISOString().slice(0, 10));
const events = ref([]);
const completedEvents = ref([]);
const loading = ref(false);
const errorMessage = ref("");

const form = ref({
  id: "",
  title: "",
  start: "09:00",
  end: "10:00",
  note: "",
  fixed: false,
  category: "学习",
  location: "",
  description: "",
  priority: 2,
});
const isEditing = ref(false);

const aiPrompt = ref("");
const aiLoading = ref(false);
const aiApplied = ref([]);
const aiErrors = ref([]);
const aiModel = ref("");
const aiMessage = ref("");
const aiRawActions = ref([]);
const aiSummary = ref("");
const aiStages = ref([]);
const aiStageIndex = ref(-1);
const aiPromptTemplate = ref("");
const aiStageTimer = ref(null);
const freshEventIds = ref(new Set());

const sortedEvents = computed(() =>
  [...events.value].sort((a, b) => a.start_min - b.start_min)
);

const sortedCompletedEvents = computed(() =>
  [...completedEvents.value].sort((a, b) => a.start_min - b.start_min)
);

const hourMarks = computed(() => {
  const marks = [];
  for (let h = HOUR_START; h <= HOUR_END; h += 1) {
    marks.push(h);
  }
  return marks;
});

const weekDays = computed(() => {
  const date = new Date(selectedDate.value);
  const day = date.getDay();
  const offset = day === 0 ? 6 : day - 1;
  const monday = new Date(date);
  monday.setDate(date.getDate() - offset);
  const list = [];
  for (let i = 0; i < 7; i += 1) {
    const d = new Date(monday);
    d.setDate(monday.getDate() + i);
    const iso = d.toISOString().slice(0, 10);
    list.push({
      date: iso,
      label: `${d.getMonth() + 1}/${d.getDate()}`,
      weekday: ["一", "二", "三", "四", "五", "六", "日"][i],
    });
  }
  return list;
});

const calendarBlocks = computed(() => {
  const startMin = HOUR_START * 60;
  return sortedEvents.value
    .filter((item) => item.end_min > startMin && item.start_min < HOUR_END * 60)
    .map((item) => {
      const clampedStart = Math.max(item.start_min, startMin);
      const clampedEnd = Math.min(item.end_min, HOUR_END * 60);
      const top = ((clampedStart - startMin) / 60) * HOUR_HEIGHT;
      const height = Math.max(24, ((clampedEnd - clampedStart) / 60) * HOUR_HEIGHT);
      return {
        ...item,
        top,
        height,
      };
    });
});

function timeToMin(value) {
  const [h, m] = value.split(":").map(Number);
  return h * 60 + m;
}

function minToTime(mins) {
  const h = String(Math.floor(mins / 60)).padStart(2, "0");
  const m = String(mins % 60).padStart(2, "0");
  return `${h}:${m}`;
}

function formatApplied(item) {
  const base = `${item.action} ${item.title || item.event_id || ""}`.trim();
  if (item.source_date && item.target_date && item.source_date !== item.target_date) {
    return `${base}（${item.source_date} -> ${item.target_date}）`;
  }
  if (item.target_date) {
    return `${base}（${item.target_date}）`;
  }
  return base;
}

async function fetchSchedule() {
  loading.value = true;
  errorMessage.value = "";
  try {
    const res = await axios.get(`${API_BASE}/api/schedule`, {
      params: { date: selectedDate.value },
    });
    events.value = res.data.data.events || [];
    completedEvents.value = res.data.data.completed || [];
  } catch (err) {
    errorMessage.value =
      err?.response?.data?.detail?.message ||
      err?.response?.data?.detail ||
      err.message;
  } finally {
    loading.value = false;
  }
}

async function fetchAiConfig() {
  try {
    const res = await axios.get(`${API_BASE}/api/ai/config`);
    aiPromptTemplate.value = res?.data?.data?.system_prompt || "";
  } catch {
    aiPromptTemplate.value = "";
  }
}

function resetForm() {
  form.value = {
    id: "",
    title: "",
    start: "09:00",
    end: "10:00",
    note: "",
    fixed: false,
    category: "学习",
    location: "",
    description: "",
    priority: 2,
  };
  isEditing.value = false;
}

function fillForm(event) {
  form.value = {
    id: event.id,
    title: event.title,
    start: minToTime(event.start_min),
    end: minToTime(event.end_min),
    note: event.note || "",
    fixed: !!event.fixed,
    category: event.category || "学习",
    location: event.location || "",
    description: event.description || "",
    priority: event.priority || 2,
  };
  isEditing.value = true;
}

async function submitEvent() {
  errorMessage.value = "";
  const payload = {
    date: selectedDate.value,
    title: form.value.title.trim(),
    start_min: timeToMin(form.value.start),
    end_min: timeToMin(form.value.end),
    note: form.value.note.trim(),
    fixed: !!form.value.fixed,
    category: form.value.category.trim() || "学习",
    location: form.value.location.trim(),
    description: form.value.description.trim(),
    priority: Number(form.value.priority) || 2,
  };
  if (!payload.title) {
    errorMessage.value = "标题不能为空";
    return;
  }
  if (payload.start_min >= payload.end_min) {
    errorMessage.value = "开始时间必须早于结束时间";
    return;
  }
  try {
    let addedId = "";
    if (isEditing.value) {
      await axios.patch(`${API_BASE}/api/events/${form.value.id}`, payload);
    } else {
      const res = await axios.post(`${API_BASE}/api/events`, payload);
      addedId = res?.data?.data?.id || "";
    }
    resetForm();
    await fetchSchedule();
    if (addedId) {
      freshEventIds.value.add(addedId);
      setTimeout(() => {
        freshEventIds.value.delete(addedId);
      }, 900);
    }
  } catch (err) {
    errorMessage.value =
      err?.response?.data?.detail?.message ||
      err?.response?.data?.detail ||
      err.message;
  }
}

async function deleteEvent(id) {
  if (!window.confirm("确认删除该事件？")) return;
  errorMessage.value = "";
  try {
    await axios.delete(`${API_BASE}/api/events/${id}`, {
      params: { date: selectedDate.value },
    });
    await fetchSchedule();
  } catch (err) {
    errorMessage.value =
      err?.response?.data?.detail?.message ||
      err?.response?.data?.detail ||
      err.message;
  }
}

async function completeEvent(id) {
  errorMessage.value = "";
  try {
    await axios.post(`${API_BASE}/api/events/${id}/complete`, {
      date: selectedDate.value,
      completed: true,
    });
    await fetchSchedule();
  } catch (err) {
    errorMessage.value =
      err?.response?.data?.detail?.message ||
      err?.response?.data?.detail ||
      err.message;
  }
}

async function restoreEvent(id) {
  errorMessage.value = "";
  try {
    await axios.post(`${API_BASE}/api/events/${id}/complete`, {
      date: selectedDate.value,
      completed: false,
    });
    await fetchSchedule();
  } catch (err) {
    errorMessage.value =
      err?.response?.data?.detail?.message ||
      err?.response?.data?.detail ||
      err.message;
  }
}

async function runAiReplan() {
  if (!aiPrompt.value.trim()) return;
  aiLoading.value = true;
  aiMessage.value = "";
  aiApplied.value = [];
  aiErrors.value = [];
  aiRawActions.value = [];
  aiSummary.value = "";
  aiStages.value = ["解析用户需求", "检查时间冲突", "生成调整动作", "应用到课表"];
  aiStageIndex.value = 0;
  if (aiStageTimer.value) clearInterval(aiStageTimer.value);
  aiStageTimer.value = setInterval(() => {
    if (aiStageIndex.value < aiStages.value.length - 1) {
      aiStageIndex.value += 1;
    }
  }, 700);
  try {
    const before = sortedEvents.value.map((item) => ({
      id: item.id,
      start_min: item.start_min,
      end_min: item.end_min,
    }));
    const res = await axios.post(`${API_BASE}/api/ai/replan`, {
      date: selectedDate.value,
      prompt: aiPrompt.value.trim(),
    });
    const data = res.data.data;
    aiApplied.value = data.applied || [];
    aiErrors.value = data.errors || [];
    aiRawActions.value = data.raw_actions || [];
    aiSummary.value = data.llm_summary || "";
    aiModel.value = data.model_used || "";
    aiMessage.value = res.data.message || "AI 已处理";
    await fetchSchedule();
    const moved = sortedEvents.value
      .filter((item) => {
        const old = before.find((x) => x.id === item.id);
        return old && (old.start_min !== item.start_min || old.end_min !== item.end_min);
      })
      .map((x) => x.id);
    moved.forEach((id) => {
      freshEventIds.value.add(id);
      setTimeout(() => freshEventIds.value.delete(id), 1200);
    });
  } catch (err) {
    aiMessage.value =
      err?.response?.data?.detail?.message ||
      err?.response?.data?.detail ||
      err.message;
  } finally {
    if (aiStageTimer.value) clearInterval(aiStageTimer.value);
    aiStageIndex.value = aiStages.value.length - 1;
    aiLoading.value = false;
  }
}

onMounted(async () => {
  await Promise.all([fetchSchedule(), fetchAiConfig()]);
});
</script>

<template>
  <div class="page">
    <header class="top">
      <div class="brand">
        <span class="logo">M</span>
        <div>
          <h1>Momentum</h1>
          <p class="tagline">自然语言调课 · 冲突校验 · 跨天移动</p>
        </div>
      </div>
      <label class="date-box">
        日期
        <input v-model="selectedDate" type="date" @change="fetchSchedule" />
      </label>
    </header>

    <section class="week-strip">
      <button
        v-for="d in weekDays"
        :key="d.date"
        :class="['day-chip', { active: d.date === selectedDate }]"
        @click="selectedDate = d.date; fetchSchedule()"
      >
        <span>周{{ d.weekday }}</span>
        <strong>{{ d.label }}</strong>
      </button>
    </section>

    <p v-if="errorMessage" class="error">{{ errorMessage }}</p>

    <main class="layout">
      <section class="panel">
        <h2>日历视图（单日）</h2>
        <div class="calendar">
          <div class="hours">
            <span
              v-for="h in hourMarks"
              :key="h"
              class="hour-tick"
              :style="{ top: `${(h - HOUR_START) * HOUR_HEIGHT}px` }"
            >{{ String(h).padStart(2, "0") }}:00</span>
          </div>
          <div class="grid">
            <div
              v-for="h in hourMarks.slice(0, -1)"
              :key="`line-${h}`"
              class="grid-line"
              :style="{ top: `${(h - HOUR_START) * HOUR_HEIGHT}px` }"
            />
            <transition-group name="block" tag="div">
              <button
                v-for="item in calendarBlocks"
                :key="item.id"
                class="calendar-block"
                :class="[
                  `p-${item.priority || 2}`,
                  { fresh: freshEventIds.has(item.id), fixed: item.fixed },
                ]"
                :style="{ top: `${item.top}px`, height: `${item.height}px` }"
                @click="fillForm(item)"
              >
                <strong>{{ item.title }}</strong>
                <small>{{ minToTime(item.start_min) }} - {{ minToTime(item.end_min) }}</small>
                <small>{{ item.category || "学习" }} · P{{ item.priority || 2 }}</small>
              </button>
            </transition-group>
          </div>
        </div>

        <h3>事件清单</h3>
        <p v-if="loading" class="muted">加载中...</p>
        <transition-group v-else-if="sortedEvents.length" tag="ul" class="event-list" name="item">
          <li
            v-for="item in sortedEvents"
            :key="item.id"
            class="event-item"
            :class="{ fresh: freshEventIds.has(item.id) }"
          >
            <div>
              <p class="event-title">
                {{ item.title }}
                <span v-if="item.fixed" class="tag">fixed</span>
              </p>
              <p class="muted">{{ minToTime(item.start_min) }} - {{ minToTime(item.end_min) }}</p>
              <p class="muted">分类：{{ item.category || "学习" }} | 优先级：P{{ item.priority || 2 }}</p>
              <p v-if="item.location" class="muted">地点：{{ item.location }}</p>
              <p v-if="item.description" class="muted">详情：{{ item.description }}</p>
              <p v-if="item.note" class="muted">{{ item.note }}</p>
            </div>
            <div class="actions">
              <button @click="fillForm(item)">编辑</button>
              <button class="danger" @click="deleteEvent(item.id)">删除</button>
              <button class="ok" @click="completeEvent(item.id)">完成</button>
            </div>
          </li>
        </transition-group>
        <p v-else class="muted">今天还没有事件</p>

        <h3>已完成</h3>
        <transition-group v-if="sortedCompletedEvents.length" class="event-list completed" name="done" tag="ul">
          <li v-for="item in sortedCompletedEvents" :key="item.id" class="event-item">
            <div>
              <p class="event-title">{{ item.title }}</p>
              <p class="muted">{{ minToTime(item.start_min) }} - {{ minToTime(item.end_min) }}</p>
            </div>
            <button @click="restoreEvent(item.id)">恢复</button>
          </li>
        </transition-group>
        <p v-else class="muted">暂无已完成事件</p>
      </section>

      <section class="panel">
        <h2>{{ isEditing ? "编辑事件" : "新增事件" }}</h2>
        <div class="form-grid">
          <label>标题<input v-model="form.title" type="text" placeholder="例如：Read 3.2" /></label>
          <label>开始<input v-model="form.start" type="time" /></label>
          <label>结束<input v-model="form.end" type="time" /></label>
          <label>分类<input v-model="form.category" type="text" placeholder="学习/课程/会议" /></label>
          <label>地点<input v-model="form.location" type="text" placeholder="图书馆A201" /></label>
          <label>优先级
            <select v-model.number="form.priority">
              <option :value="1">P1 高</option>
              <option :value="2">P2 中</option>
              <option :value="3">P3 低</option>
            </select>
          </label>
          <label>描述<textarea v-model="form.description" rows="2" placeholder="更细任务描述（可选）" /></label>
          <label>备注<input v-model="form.note" type="text" placeholder="可选" /></label>
          <label class="check"><input v-model="form.fixed" type="checkbox" /> fixed（不允许 AI 改时间）</label>
        </div>
        <div class="actions">
          <button class="ok" @click="submitEvent">{{ isEditing ? "保存修改" : "创建事件" }}</button>
          <button v-if="isEditing" @click="resetForm">取消编辑</button>
        </div>

        <h2>AI 指令</h2>
        <p class="hint">可直接说人话；未写具体时间时，系统会按默认晚间占用策略处理「今晚有事」类需求。</p>
        <textarea
          v-model="aiPrompt"
          rows="4"
          placeholder="例：今晚临时有事，帮我把能挪的学习任务挪到明天 / 把「高数复习」挪到明天晚上"
        />
        <div class="chip-row">
          <button type="button" class="chip" @click="aiPrompt = '今晚临时有事，帮我调整今天的课表'">今晚有事</button>
          <button type="button" class="chip" @click="aiPrompt = '把今天排不下的学习任务挪到明天，尽量别动高优先级'">挪到明天</button>
          <button type="button" class="chip" @click="aiPrompt = '我现在只有45分钟，帮我安排一个能完成的任务'">碎片45分钟</button>
        </div>
        <div class="actions">
          <button class="ok" :disabled="aiLoading" @click="runAiReplan">
            {{ aiLoading ? "AI处理中..." : "让 AI 重排" }}
          </button>
        </div>

        <div v-if="aiLoading" class="ai-stage-box">
          <p class="muted">AI 正在工作中...</p>
          <ol>
            <li
              v-for="(step, idx) in aiStages"
              :key="step"
              :class="{ active: idx <= aiStageIndex }"
            >
              {{ step }}
            </li>
          </ol>
        </div>

        <p v-if="aiMessage" class="muted">{{ aiMessage }}</p>
        <p v-if="aiModel" class="muted">模型：{{ aiModel }}</p>
        <div v-if="aiSummary" class="ai-summary">
          <strong>本轮思路</strong>
          <p>{{ aiSummary }}</p>
        </div>
        <details v-if="aiPromptTemplate" class="details">
          <summary>查看 AI 系统提示词</summary>
          <pre>{{ aiPromptTemplate }}</pre>
        </details>
        <details v-if="aiRawActions.length" class="details">
          <summary>查看 AI 原始动作</summary>
          <pre>{{ JSON.stringify(aiRawActions, null, 2) }}</pre>
        </details>
        <ul v-if="aiApplied.length" class="result ok-list">
          <li v-for="(item, idx) in aiApplied" :key="idx">
            {{ formatApplied(item) }}
          </li>
        </ul>
        <ul v-if="aiErrors.length" class="result err-list">
          <li v-for="(item, idx) in aiErrors" :key="idx">
            {{ item.error }}
          </li>
        </ul>
      </section>
    </main>
  </div>
</template>

<style scoped>
.page {
  min-height: 100vh;
  padding: 24px 20px 40px;
  background: radial-gradient(1200px 600px at 10% -10%, #e0f2fe 0%, transparent 55%),
    radial-gradient(900px 500px at 100% 0%, #ede9fe 0%, transparent 50%),
    linear-gradient(180deg, #f8fafc 0%, #eef2ff 100%);
  color: #0f172a;
}

.top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: linear-gradient(135deg, #0ea5e9, #6366f1);
  color: #fff;
  font-weight: 800;
  font-size: 18px;
  display: grid;
  place-items: center;
  box-shadow: 0 8px 20px rgba(14, 165, 233, 0.35);
}

.top h1 {
  margin: 0;
  font-size: 22px;
  letter-spacing: -0.02em;
}

.tagline {
  margin: 2px 0 0;
  font-size: 12px;
  color: #64748b;
}

.date-box {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}

.layout {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.week-strip {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  overflow-x: auto;
}

.day-chip {
  border: 1px solid rgba(148, 163, 184, 0.45);
  background: rgba(255, 255, 255, 0.75);
  backdrop-filter: blur(8px);
  border-radius: 12px;
  padding: 8px 12px;
  min-width: 82px;
  display: grid;
  gap: 3px;
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.day-chip:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(15, 23, 42, 0.08);
}

.day-chip.active {
  background: linear-gradient(135deg, #0ea5e9, #6366f1);
  color: #fff;
  border-color: transparent;
  box-shadow: 0 8px 22px rgba(99, 102, 241, 0.35);
}

.panel {
  background: rgba(255, 255, 255, 0.88);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(226, 232, 240, 0.9);
  border-radius: 16px;
  padding: 18px;
  box-shadow: 0 12px 40px rgba(15, 23, 42, 0.08);
}

.panel h2 {
  margin: 0 0 10px;
  font-size: 18px;
}

.panel h3 {
  margin: 16px 0 10px;
  font-size: 16px;
}

.calendar {
  display: grid;
  grid-template-columns: 62px 1fr;
  gap: 10px;
  margin-bottom: 12px;
}

.hours {
  height: calc((24 - 6) * 56px);
  position: relative;
}

.hour-tick {
  position: absolute;
  left: 0;
  transform: translateY(-50%);
  color: #64748b;
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.grid {
  position: relative;
  height: calc((24 - 6) * 56px);
  border: 1px solid rgba(226, 232, 240, 0.95);
  border-radius: 14px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  overflow: auto;
}

.grid-line {
  position: absolute;
  left: 0;
  right: 0;
  border-top: 1px dashed #dbe5f2;
}

.calendar-block {
  position: absolute;
  left: 8px;
  right: 8px;
  border: none;
  border-radius: 12px;
  padding: 8px 10px;
  text-align: left;
  color: #0f172a;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.06);
  transition: top 0.45s ease, height 0.45s ease, transform 0.25s ease, opacity 0.25s ease, box-shadow 0.2s ease;
  display: grid;
  gap: 2px;
}

.calendar-block:hover {
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.1);
  transform: scale(1.01);
}

.calendar-block strong {
  font-size: 13px;
}

.calendar-block small {
  font-size: 12px;
  color: #334155;
}

.calendar-block.p-1 { background: #fecaca; }
.calendar-block.p-2 { background: #bfdbfe; }
.calendar-block.p-3 { background: #bbf7d0; }
.calendar-block.fixed { outline: 2px solid #0f172a33; }
.calendar-block.fresh { animation: pulse 0.8s ease; }

.event-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 10px;
}

.event-item {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 10px;
  display: flex;
  justify-content: space-between;
  gap: 10px;
}

.event-item.fresh {
  animation: pulse 0.8s ease;
}

.completed .event-item {
  opacity: 0.75;
}

.event-title {
  margin: 0 0 4px;
  font-weight: 600;
}

.tag {
  font-size: 12px;
  background: #e2e8f0;
  color: #334155;
  border-radius: 999px;
  padding: 2px 8px;
  margin-left: 8px;
}

.muted {
  margin: 0;
  color: #64748b;
  font-size: 13px;
}

.hint {
  margin: 0 0 8px;
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
}

.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 8px 0 4px;
}

.chip {
  font-size: 12px;
  padding: 6px 10px;
  border-radius: 999px;
  background: #e0f2fe;
  color: #0369a1;
  border: 1px solid #bae6fd;
  cursor: pointer;
}

.chip:hover {
  filter: brightness(0.97);
}

.ai-summary {
  margin-top: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  font-size: 13px;
}

.ai-summary strong {
  display: block;
  margin-bottom: 4px;
  color: #166534;
}

.ai-summary p {
  margin: 0;
  color: #14532d;
  line-height: 1.5;
}

.form-grid {
  display: grid;
  gap: 10px;
}

.form-grid label {
  display: grid;
  gap: 6px;
  font-size: 13px;
}

.check {
  display: flex !important;
  align-items: center;
  gap: 8px;
}

input,
textarea,
button {
  font: inherit;
}

input,
textarea {
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  padding: 8px 10px;
}

select {
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  padding: 8px 10px;
  background: #fff;
}

.actions {
  margin-top: 10px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

button {
  border: none;
  border-radius: 8px;
  padding: 7px 12px;
  cursor: pointer;
  background: #e2e8f0;
}

button:hover {
  filter: brightness(0.96);
}

.ok {
  background: #10b981;
  color: #fff;
}

.danger {
  background: #ef4444;
  color: #fff;
}

.error {
  background: #fee2e2;
  color: #991b1b;
  border: 1px solid #fecaca;
  border-radius: 8px;
  padding: 8px 10px;
  margin: 0 0 12px;
}

.result {
  margin: 8px 0 0;
  padding-left: 18px;
  font-size: 13px;
}

.ok-list {
  color: #0f766e;
}

.err-list {
  color: #b91c1c;
}

.ai-stage-box {
  margin-top: 10px;
  padding: 10px;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #eff6ff;
}

.ai-stage-box ol {
  margin: 8px 0 0;
  padding-left: 18px;
}

.ai-stage-box li {
  color: #64748b;
}

.ai-stage-box li.active {
  color: #0369a1;
  font-weight: 600;
}

.details {
  margin-top: 10px;
}

.details pre {
  white-space: pre-wrap;
  word-break: break-word;
  padding: 8px;
  border-radius: 8px;
  background: #f1f5f9;
  font-size: 12px;
  max-height: 180px;
  overflow: auto;
}

.item-enter-active,
.item-leave-active,
.done-enter-active,
.done-leave-active,
.block-enter-active,
.block-leave-active {
  transition: all 0.25s ease;
}

.item-enter-from,
.done-enter-from,
.block-enter-from {
  opacity: 0;
  transform: translateY(-6px);
}

.item-leave-to,
.done-leave-to,
.block-leave-to {
  opacity: 0;
  transform: translateX(10px);
}

@keyframes pulse {
  0% { box-shadow: 0 0 0 0 rgba(14, 165, 233, 0.5); }
  100% { box-shadow: 0 0 0 10px rgba(14, 165, 233, 0); }
}

@media (max-width: 900px) {
  .layout {
    grid-template-columns: 1fr;
  }
}
</style>