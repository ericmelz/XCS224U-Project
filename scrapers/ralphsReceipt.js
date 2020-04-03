// Disable Content-Security-Policy by clicking on the chrome extension
// Click artoo bookmarklet
// Navigate to purchase page

function fname(url) {
  let x = url.substring(url.lastIndexOf('/')+1)+ "_raw.json";
  x = x.replace(/~/g, '_');
  console.log(`x is ${x}`);
  return x;
}
function save(data) {
  artoo.savePrettyJson(data, {filename:fname(document.URL)});
}
function doScrape() {
  return artoo.scrape('div.imageTextLineCenter', 'text', save);
}
doScrape();

