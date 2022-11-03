import re
from channels.testing import ChannelsLiveServerTestCase
from playwright.sync_api import expect, sync_playwright
from adit.accounts.factories import UserFactory


class SomeLiveTests(ChannelsLiveServerTestCase):
    def setUp(self):
        super().setUp()
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch()

    def tearDown(self):
        self.browser.close()
        self.playwright.stop()
        super().tearDown()

    def test_login(self):
        password = "mysecret"
        user = UserFactory(password=password)

        page = self.browser.new_page()
        print(self.live_server_url)
        page.goto(self.live_server_url + "/accounts/login")
        page.get_by_label("Username").fill(user.username)
        page.get_by_label("Password").fill(password)
        page.get_by_text("Log in").click()

        # page.screenshot(path="foobar.png")

        # assert page.url == "%s%s" % (self.live_server_url, "/profile/")
        expect(page).to_have_title(re.compile("ADIT"))
