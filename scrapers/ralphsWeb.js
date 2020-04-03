// Disable Content-Security-Policy by clicking on the chrome extension
// Click artoo bookmarklet
// Navigate to purchase page

function fname(url) {
  let x = url.substring(url.lastIndexOf('/')+1)+ "_web.json";
  x = x.replace(/~/g, '_');
  return x;
}
function save(data) {
  artoo.savePrettyJson(data, {filename:fname(document.URL)});
}
function doScrape() {
  return artoo.scrape(
    'div.PH-ProductCard-item-description > a',
    {
      title: 'text',
      id: function($) {
        var x = $(this).attr('href');
        x = x.substring(x.lastIndexOf('/') + 1);
        return x;
      }
    },
    save
  );
}
doScrape();
