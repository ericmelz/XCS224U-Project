// Disable Content-Security-Policy by clicking on the chrome extension
// Click artoo bookmarklet
// Navigate to My Purchases

var scraper = {
  iterator: 'a.kds-Link.kds-Link--inherit[aria-label^=View]',
  data: 'href'
}

function nextUrl(page) {
  return 'https://www.ralphs.com' + page.find('a.Pagination-link:last').attr('href');
}

var frontPage = artoo.scrape(scraper)

artoo.ajaxSpider(
  function(i, $data) {
    var page = null;
    if (!i) {
      page = artoo.$(document);
    } else {
      var p0 = $data[0]
      console.log('p0');
      console.log(p0);
      var inner = p0.innerHTML;
      console.log('inner');
      console.log(inner);
      var page = artoo.$.parseHTML(inner, null, true);
      console.log('page');
      console.log(page);
    }
    var url = nextUrl(page);
    console.log('i is ' + i + ', url=' + url);
    return url;
  },
  {
    limit: 2,
    scrape: scraper,
    concat: true,
    done: function(data) {
      artoo.log.debug('Finished retrieving data. Downloading...');
      artoo.savePrettyJson(
        frontPage.concat(data),
        {filename: 'ralphs_purchases.json'}
      );
    }
  }
);
