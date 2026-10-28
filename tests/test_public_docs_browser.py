"""Real static browser DOM checks, driven by Python with WebGL disabled."""
import json,threading
import pytest
from test_public_docs import tool


@pytest.fixture
def browser_site():
    server=tool('serve_docs').create_server();thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        with tool('headless_browser').Browser() as browser:yield browser,'http://127.0.0.1:'+str(server.server_port)
    finally:server.shutdown();server.server_close();thread.join(timeout=5)


def test_generated_home_cards_and_full_roadmap_render_without_node_or_page_errors(browser_site):
    browser,origin=browser_site
    browser.navigate(origin+'/index.html');browser.wait('document.querySelector("#latest-task-number").textContent === "Task 228"')
    assert browser.evaluate('document.querySelector("#next-task-number").textContent')=='Task 209'
    assert browser.evaluate('document.querySelectorAll("#task-status-index > li").length')==227
    assert browser.errors()==[]
    browser.navigate(origin+'/tasks.html');browser.wait('document.querySelectorAll(".task-item").length === 227')
    assert browser.evaluate('document.querySelector(".task-item").id')=='task-228'
    assert 'Superseded' in browser.evaluate('document.querySelector("#task-213").textContent')
    assert 'Not done' in browser.evaluate('document.querySelector("#task-204").textContent')
    assert 'Source-verified' in browser.evaluate('document.querySelector("#task-226").textContent')
    assert browser.errors()==[]


def test_every_static_page_initializes_and_keeps_mobile_content_inside_the_view(browser_site):
    browser,origin=browser_site
    browser.call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':False})
    for page in tool('serve_docs').PAGES:
        browser.navigate(origin+'/'+page)
        if page in {'index.html','roadmap.html'}:browser.wait('!document.querySelector("#latest-task-number").textContent.includes("Loading")')
        if page=='tasks.html':browser.wait('document.querySelectorAll(".task-item").length === 227')
        assert browser.evaluate('!!document.querySelector("main#main")'),page
        assert browser.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1'),page
        assert browser.errors()==[],(page,browser.errors())


def test_browser_renderer_treats_untrusted_task_titles_as_text(browser_site):
    browser,origin=browser_site;browser.navigate(origin+'/index.html')
    attack='<img src=x onerror="window.__injected=true">'
    expression='''(async()=>{const {renderTaskDirectory}=await import('/roadmap-status.js');
      const target=document.createElement('ol');document.body.append(target);
      renderTaskDirectory(target,[{number:999,title:TITLE,description:'Untrusted data',category:'Test',status:'planned'}]);
      return {text:target.textContent,images:target.querySelectorAll('img').length,injected:!!window.__injected};})()'''.replace('TITLE',json.dumps(attack))
    result=browser.evaluate(expression)
    assert attack in result['text'] and result['images']==0 and result['injected'] is False
