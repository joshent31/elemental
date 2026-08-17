from setuptools import setup, find_packages

with open("requirements.txt") as f:
    install_requires = f.read().strip().split("\n")

setup(
    name="elemental_erp",
    version="0.1.0",
    description="Retail Furniture Manufacturing tracking app (Job -> Purchase -> Production -> Packaging -> Dispatch) with QR based process tracking, built on Frappe/ERPNext v15",
    author="Elemental Fixtures Pvt Ltd",
    author_email="dev@elemental.com",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires,
)
