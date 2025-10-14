        # Create company
        Party = Pool.get('party.party')
        party_company = Party(name='Company')
        party_company.save()
        Company = Pool.get('company.company')
        company = Company(party=party_company, currency=1)  # Assume USD id 1
        company.save()

        # Create fiscal year
        fiscalyear = set_fiscalyear_invoice_sequences(
            create_fiscalyear(company, today))
        fiscalyear.click('create_period')
