async function loadComponent(id, file) {
  const res = await fetch(file);
  const data = await res.text();
  document.getElementById(id).innerHTML = data;
}