# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/Snuffy2/hass-variables/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                           |    Stmts |     Miss |   Branch |   BrPart |   Cover |   Missing |
|----------------------------------------------- | -------: | -------: | -------: | -------: | ------: | --------: |
| custom\_components/variable/\_\_init\_\_.py    |      209 |        1 |       88 |        7 |     97% |180-\>182, 182-\>184, 298, 379-\>378, 547-\>549, 569-\>571, 571-\>575 |
| custom\_components/variable/binary\_sensor.py  |      208 |       46 |       80 |       19 |     75% |114-118, 153, 188, 229, 232-237, 249-252, 259-260, 271-274, 281-282, 348, 357-363, 392-398, 406-\>424, 411-418, 432, 434-\>453, 472-\>479, 481-508, 522 |
| custom\_components/variable/config\_flow.py    |      576 |       74 |      246 |       51 |     83% |408, 428-\>430, 430-\>434, 507, 513-\>515, 525, 545-553, 614, 650, 787, 862-872, 886, 889-890, 906-912, 933, 949, 981, 989-\>1002, 1034, 1036, 1040, 1066, 1098, 1106-\>1133, 1112-\>1114, 1114-\>1116, 1117, 1119, 1122-\>1124, 1124-\>1126, 1147, 1203, 1219, 1291, 1325, 1427-1432, 1441-1442, 1446-\>1469, 1447-\>1449, 1454-\>1458, 1474, 1557-1568, 1577-1610, 1624, 1656, 1695, 1837, 1920, 1929, 1960, 2044, 2080-\>2082 |
| custom\_components/variable/const.py           |       38 |        0 |        0 |        0 |    100% |           |
| custom\_components/variable/device.py          |       59 |        0 |       22 |        1 |     99% | 144-\>140 |
| custom\_components/variable/device\_tracker.py |      179 |       14 |       66 |        7 |     91% |118-122, 173, 228-229, 325-331, 339-\>357, 344-351, 365, 417-\>419 |
| custom\_components/variable/helpers.py         |      169 |        1 |       98 |        2 |     99% |98-\>100, 356 |
| custom\_components/variable/sensor.py          |      235 |       43 |       78 |       14 |     80% |153, 191-192, 219-220, 242-275, 301-302, 358, 362-368, 400-406, 414-\>432, 426, 432-\>446, 454, 505-511, 524, 566, 571-579, 592 |
| **TOTAL**                                      | **1673** |  **179** |  **678** |  **101** | **87%** |           |


## Setup coverage badge

Below are examples of the badges you can use in your main branch `README` file.

### Direct image

[![Coverage badge](https://raw.githubusercontent.com/Snuffy2/hass-variables/python-coverage-comment-action-data/badge.svg)](https://htmlpreview.github.io/?https://github.com/Snuffy2/hass-variables/blob/python-coverage-comment-action-data/htmlcov/index.html)

This is the one to use if your repository is private or if you don't want to customize anything.

### [Shields.io](https://shields.io) Json Endpoint

[![Coverage badge](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Snuffy2/hass-variables/python-coverage-comment-action-data/endpoint.json)](https://htmlpreview.github.io/?https://github.com/Snuffy2/hass-variables/blob/python-coverage-comment-action-data/htmlcov/index.html)

Using this one will allow you to [customize](https://shields.io/endpoint) the look of your badge.
It won't work with private repositories. It won't be refreshed more than once per five minutes.

### [Shields.io](https://shields.io) Dynamic Badge

[![Coverage badge](https://img.shields.io/badge/dynamic/json?color=brightgreen&label=coverage&query=%24.message&url=https%3A%2F%2Fraw.githubusercontent.com%2FSnuffy2%2Fhass-variables%2Fpython-coverage-comment-action-data%2Fendpoint.json)](https://htmlpreview.github.io/?https://github.com/Snuffy2/hass-variables/blob/python-coverage-comment-action-data/htmlcov/index.html)

This one will always be the same color. It won't work for private repos. I'm not even sure why we included it.

## What is that?

This branch is part of the
[python-coverage-comment-action](https://github.com/marketplace/actions/python-coverage-comment)
GitHub Action. All the files in this branch are automatically generated and may be
overwritten at any moment.