async function loadProperties() {
  try {
    const res = await fetch("http://127.0.0.1:8000/api/properties/");
    const data = await res.json();

    const container = document.getElementById("propertyContainer");

    if (!container) return;

    if (data.length === 0) {
      container.innerHTML = "<p>No properties found</p>";
      return;
    }

    let html = "";

    data.forEach(p => {
      html += `
        <div class="bg-white rounded-xl overflow-hidden shadow hover:shadow-xl transition">

          <div class="h-60">
            <img src="${p.image || 'https://via.placeholder.com/400'}"
                 class="w-full h-full object-cover"/>
          </div>

          <div class="p-5 space-y-2">
            <h3 class="text-lg font-bold">${p.title}</h3>
            <p class="text-sm text-gray-500">${p.location}</p>

            <p class="text-blue-600 font-extrabold">₹${p.price}</p>

            <div class="flex justify-between mt-4">
              <button onclick="viewProperty(${p.id})"
                      class="text-blue-600 text-sm">
                View
              </button>
            </div>
          </div>

        </div>
      `;
    });

    container.innerHTML = html;

  } catch (err) {
    console.log("Error:", err);
  }
}

function viewProperty(id) {
  window.location.href = `/property_detail_view.html?id=${id}`;
}

// AUTO RUN ONLY ON THIS PAGE
document.addEventListener("DOMContentLoaded", () => {
  if (document.getElementById("propertyContainer")) {
    loadProperties();
  }
});