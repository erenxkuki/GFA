const API = (localStorage.getItem("gfa_api") || "http://localhost:8000");

function setView(html) { document.getElementById("app").innerHTML = html; }

async function api(path, opts={}) {
  const res = await fetch(API + path, { headers: {"Content-Type":"application/json"}, ...opts });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function homeView() {
  setView(`
    <section class="card">
      <h1>GFA Adapter Registry</h1>
      <p class="muted">Discover, publish, and manage game adapters for Gaming For AI.</p>
      <div class="row">
        <button onclick="location.hash='#explore'">Explore adapters</button>
        <button class="secondary" onclick="location.hash='#publish'">Publish an adapter</button>
      </div>
    </section>
    <section class="card">
      <h2>How it works</h2>
      <ol>
        <li>Developers build adapters with the GFA SDK and host them in their own repositories.</li>
        <li>Submit repository + manifest to the registry.</li>
        <li>Users discover and install adapters with compatibility checks.</li>
      </ol>
    </section>
  `);
}

async function exploreView() {
  const q = (document.getElementById("q")?.value || "");
  const status = (document.getElementById("status")?.value || "");
  let url = `/adapters?limit=20&offset=0`;
  if (q) url += `&q=${encodeURIComponent(q)}`;
  if (status) url += `&status=${encodeURIComponent(status)}`;
  let data;
  try { data = await api(url); }
  catch (e) { setView(`<section class="card"><h2>Explore</h2><p class="muted">API error: ${e.message}</p></section>`); return; }
  const items = data.items || [];
  setView(`
    <section class="card">
      <h2>Explore adapters</h2>
      <div class="row">
        <input id="q" placeholder="Search..." value="${q}" />
        <select id="status">
          <option value="">All</option>
          <option value="approved" ${status==='approved'?'selected':''}>Approved</option>
          <option value="pending" ${status==='pending'?'selected':''}>Pending</option>
        </select>
        <button onclick="exploreView()">Search</button>
      </div>
    </section>
    <section>
      <div class="grid">
        ${items.map(a => `
          <div class="card">
            <h3>${a.name}</h3>
            <p class="muted">${a.description || ''}</p>
            <div>${(a.capabilities||[]).map(c=>`<span class="badge">${c}</span>`).join('')}</div>
            <p class="muted">by ${a.author || 'unknown'} · ${a.status || ''}</p>
            <button class="secondary" onclick="detailView('${a.id}')">Details</button>
          </div>
        `).join('') || '<p class="muted">No adapters found.</p>'}
      </div>
    </section>
  `);
}

async function detailView(id) {
  let a;
  try { a = await api(`/adapters/${id}`); }
  catch (e) { setView(`<section class="card"><p class="muted">Error: ${e.message}</p></section>`); return; }
  setView(`
    <section class="card">
      <h2>${a.name}</h2>
      <p class="muted">${a.description || ''}</p>
      <p><strong>Author:</strong> ${a.author || ''}</p>
      <p><strong>Repository:</strong> ${a.repository || ''}</p>
      <p><strong>License:</strong> ${a.license || ''}</p>
      <p><strong>Status:</strong> ${a.status || ''}</p>
      <div>${(a.capabilities||[]).map(c=>`<span class="badge">${c}</span>`).join('')}</div>
      <h3>Releases</h3>
      <pre>${JSON.stringify(a.releases || [], null, 2)}</pre>
      <h3>Verification</h3>
      <pre>${JSON.stringify(a.verification || [], null, 2)}</pre>
      <button class="secondary" onclick="exploreView()">Back</button>
    </section>
  `);
}

async function publishView() {
  setView(`
    <section class="card">
      <h2>Publish an adapter</h2>
      <p class="muted">API base: <input id="apiBase" value="${API}" style="width:300px" /> <button class="secondary" onclick="saveApi()">Save</button></p>
      <label>Repository path or URL</label>
      <input id="repo" placeholder="/path/to/adapter or https://..." />
      <label>Owner token (optional)</label>
      <input id="token" placeholder="owner token" />
      <label>Inline manifest (JSON, optional)</label>
      <textarea id="manifest" rows="8" placeholder='{"manifest_version":"1","id":"community.x","name":"X","version":"1.0.0","entrypoint":"python adapter.py"}'></textarea>
      <div class="row" style="margin-top:12px">
        <button onclick="submitAdapter()">Submit</button>
      </div>
      <pre id="result"></pre>
    </section>
    <section class="card">
      <h2>Repository ownership verification</h2>
      <p class="muted">Provide a token that matches the repository owner. The registry records ownership on submit.</p>
    </section>
  `);
}

function saveApi() {
  const v = document.getElementById("apiBase").value;
  localStorage.setItem("gfa_api", v);
  alert("Saved");
}

async function submitAdapter() {
  const repo = document.getElementById("repo").value;
  const token = document.getElementById("token").value;
  const manifestText = document.getElementById("manifest").value.trim();
  const body = { repository: repo, owner_token: token || null };
  if (manifestText) {
    try { body.manifest = JSON.parse(manifestText); }
    catch (e) { document.getElementById("result").textContent = "Invalid JSON: " + e.message; return; }
  }
  try {
    const data = await api("/adapters/submit", { method:"POST", body: JSON.stringify(body) });
    document.getElementById("result").textContent = JSON.stringify(data, null, 2);
  } catch (e) {
    document.getElementById("result").textContent = "Error: " + e.message;
  }
}

function docsView() {
  setView(`
    <section class="card">
      <h2>Developer portal</h2>
      <h3>SDK</h3>
      <p>Install: <code>pip install -e .</code></p>
      <p>Manifest fields: manifest_version, id, name, version, description, author, license, gfa_compatibility, gcl_compatibility, capabilities, entrypoint, permissions.</p>
      <h3>CLI</h3>
      <pre>gfa adapter init my-adapter
gfa adapter validate ./my-adapter
gfa adapter test ./my-adapter</pre>
      <h3>Publishing flow</h3>
      <ol>
        <li>Create adapter repository.</li>
        <li>Add manifest.json.</li>
        <li>Validate locally.</li>
        <li>Submit repository URL + manifest via Publish page.</li>
        <li>Registry runs automated checks and lists on approval.</li>
      </ol>
    </section>
  `);
}

function route() {
  const hash = location.hash || "#home";
  if (hash.startsWith("#explore")) exploreView();
  else if (hash.startsWith("#publish")) publishView();
  else if (hash.startsWith("#docs")) docsView();
  else if (hash.startsWith("#detail:")) detailView(hash.slice(8));
  else homeView();
}

window.addEventListener("hashchange", route);
window.detailView = detailView;
window.exploreView = exploreView;
window.publishView = publishView;
window.submitAdapter = submitAdapter;
window.saveApi = saveApi;
route();