# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/Snuffy2/hass-variables/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                           |    Stmts |     Miss |   Branch |   BrPart |   Cover |   Missing |
|----------------------------------------------- | -------: | -------: | -------: | -------: | ------: | --------: |
| custom\_components/variable/\_\_init\_\_.py    |      209 |       21 |       88 |       10 |     88% |136-139, 145-149, 155-164, 175, 255, 298, 336-\>335, 342, 449, 456, 492-\>494, 507-\>509, 509-\>513 |
| custom\_components/variable/binary\_sensor.py  |      208 |       51 |       80 |       26 |     70% |114-118, 153, 188, 203-\>222, 227, 229, 232-237, 249-252, 259-260, 271-274, 281-282, 348, 357-363, 387, 390-\>424, 392-398, 406-\>424, 411-418, 432, 434-\>453, 439, 442, 446, 472-\>479, 481-508, 522 |
| custom\_components/variable/config\_flow.py    |      576 |       89 |      246 |       52 |     80% |408, 428-\>430, 430-\>434, 478, 507, 513-\>515, 525, 545-553, 614, 650, 787, 800-807, 814-815, 819-\>832, 862-872, 881-912, 933, 949, 981, 989-\>1002, 1034, 1036, 1040, 1066, 1098, 1106-\>1132, 1111-\>1113, 1113-\>1115, 1116, 1118, 1121-\>1123, 1123-\>1125, 1146, 1202, 1218, 1290, 1324, 1426-1431, 1440-1441, 1445-\>1468, 1446-\>1448, 1453-\>1457, 1473, 1556-1567, 1576-1609, 1623, 1655, 1694, 1836, 1919, 1928, 1959, 2043, 2079-\>2081 |
| custom\_components/variable/const.py           |       38 |        0 |        0 |        0 |    100% |           |
| custom\_components/variable/device.py          |       59 |        0 |       22 |        1 |     99% | 144-\>140 |
| custom\_components/variable/device\_tracker.py |      179 |       14 |       66 |        7 |     91% |118-122, 173, 228-229, 325-331, 339-\>357, 344-351, 365, 417-\>419 |
| custom\_components/variable/helpers.py         |      169 |        6 |       98 |        5 |     95% |42-43, 98-99, 104, 119-\>123, 356 |
| custom\_components/variable/sensor.py          |      235 |       53 |       78 |       19 |     75% |153, 191-192, 213, 219-220, 242-275, 301-302, 358, 362-368, 395, 398-\>432, 400-406, 414-\>432, 419-426, 432-\>446, 435-441, 454, 498, 503-511, 524, 566, 571-579, 592 |
| **TOTAL**                                      | **1673** |  **234** |  **678** |  **120** | **83%** |           |


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