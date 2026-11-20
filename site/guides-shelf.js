// The home page's Personal Guides shelf: the newest guides from the site's library (/api/books).
// Where that is not served (a plain copy of this folder), the shelf keeps the guide written into
// the page.
(function () {
  var shelf = document.querySelector("[data-guides-shelf]");
  if (!shelf || !window.fetch) return;
  var lang = shelf.getAttribute("data-guides-shelf") === "ja" ? "ja" : "en";
  var count = function (n) { return lang === "ja" ? n + "章" : n + (n === 1 ? " chapter" : " chapters"); };
  fetch("/api/books?lang=" + lang, { headers: { Accept: "application/json" } })
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (data) {
      var guides = data && Array.isArray(data.guides) ? data.guides : [];
      if (!guides.length) return;
      var items = guides.map(function (g) {
        var li = document.createElement("li");
        var a = document.createElement("a");
        a.href = g.href;
        var name = document.createElement("span");
        name.className = "guides-shelf-name";
        name.textContent = g.name;
        var meta = document.createElement("span");
        meta.className = "guides-shelf-meta";
        meta.textContent = [g.rank, count(g.chapters)].filter(Boolean).join(" · ");
        var latest = document.createElement("span");
        latest.className = "guides-shelf-latest";
        latest.textContent = g.latest;
        a.append(name, meta, latest);
        li.append(a);
        return li;
      });
      shelf.replaceChildren.apply(shelf, items);
    })
    .catch(function () {});
})();
